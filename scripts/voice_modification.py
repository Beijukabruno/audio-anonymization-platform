#!/usr/bin/env python3
import numpy as np
import tempfile
import copy
import time
import logging
import os
import librosa
import librosa as rs
from audiotsm import wsola
from audiotsm.io.wav import WavReader, WavWriter
import soundfile as sf
import scipy
from scipy import signal
from scipy.io import wavfile
from scipy.signal import resample, lfilter

logger = logging.getLogger(__name__)

# vocal tract length normalization
def vtln(x, coef = 0.):
  logger.info(f"vtln() called with coef={coef}")
  start = time.time()
  
  # STFT
  mag, phase = rs.magphase(rs.core.stft(x))
  mag, phase = np.log(mag).T, phase.T

  # Frequency
  freq = np.linspace(0, np.pi, mag.shape[1]) 
  freq_warped = freq + 2.0 * np.arctan(coef * np.sin(freq) / (1 - coef * np.cos(freq)))
  
  # Warping
  mag_warped = np.zeros(mag.shape, dtype = mag.dtype)
  for t in range(mag.shape[0]):
    mag_warped[t, :] = np.interp(freq, freq_warped, mag[t, :])

  # ISTFT
  y = np.real(rs.core.istft(np.exp(mag_warped).T * phase.T)).astype(x.dtype)
  
  elapsed = time.time() - start
  logger.info(f"✓ vtln() completed in {elapsed:.2f}s")

  return y

# resampling
def resampling(x, coef = 1., fs = 16000):
  logger.info(f"\n--- resampling() START ---")
  logger.info(f"Input: shape={np.array(x).shape}, coef={coef}, fs={fs}")
  total_start = time.time()
  
  # Check which method to use
  use_fast_resamp = os.environ.get("USE_FAST_RESAMP", "0") == "1"
  use_librosa_pv = os.environ.get("USE_LIBROSA_PV", "0") == "1"
  
  if use_librosa_pv:
    logger.info(f"🎵 USING LIBROSA PHASE VOCODER (fast + pitch-preserving)")
    pv_start = time.time()
    
    # Use librosa's phase vocoder
    # speed = 1/coef because lower speed factor = higher rate parameter
    # coef=0.85 means play at 85% speed, so need to speed up by 1/0.85=1.176
    rate = 1.0 / coef  # Convert speed factor to rate multiplier
    logger.info(f"Speed factor: {coef}, Rate multiplier: {rate:.3f}")
    
    # Phase vocoder applies time-stretching
    y = librosa.phase_vocoder(x, rate)
    
    pv_elapsed = time.time() - pv_start
    logger.info(f"✓ Phase vocoder completed in {pv_elapsed:.2f}s")
    logger.info(f"  Input shape: {np.array(x).shape}")
    logger.info(f"  Output shape: {np.array(y).shape}")
    logger.info(f"  Original length: {len(x)} samples ({len(x)/fs:.2f}s)")
    logger.info(f"  Output length: {len(y)} samples ({len(y)/fs:.2f}s)")
    
    return y.astype(x.dtype)
  
  if use_fast_resamp:
    logger.info(f"⚡ USING FAST SCIPY RESAMPLING (no pitch preservation)")
    fast_start = time.time()
    
    # Fast method: use scipy directly without time-stretching
    # WARNING: This changes both pitch and tempo!
    num_samples_out = int(len(x) / coef)
    y = resample(x, num_samples_out).astype(x.dtype)
    
    fast_elapsed = time.time() - fast_start
    logger.info(f"✓ Fast resampling completed in {fast_elapsed:.2f}s")
    logger.info(f"  Input:\t{len(x)} samples ({len(x)/fs:.2f}s)")
    logger.info(f"  Output:\t{len(y)} samples ({len(y)/fs:.2f}s)")
    logger.info(f"  ⚠️  WARNING: Pitch is lowered (pitch drop due to downsampling)")
    return y
  
  # Original WSOLA-based method (slow but high quality)
  logger.info(f"Using audiotsm WSOLA (slow but timing-preserving)")
  # Create temp files
  logger.info(f"Creating temporary WAV files...")
  fn_r, fn_w = tempfile.NamedTemporaryFile(mode="r", suffix=".wav"), tempfile.NamedTemporaryFile(mode="w", suffix=".wav")  
  logger.info(f"Temp files: {fn_r.name}, {fn_w.name}")

  # Write input audio
  logger.info(f"Writing input audio to temp file...")
  write_start = time.time()
  sf.write(fn_r.name, x, fs, "PCM_16")
  write_elapsed = time.time() - write_start
  logger.info(f"✓ Write completed in {write_elapsed:.2f}s")
  
  # WSOLA processing
  logger.info(f"Opening WAV reader and writer for WSOLA processing...")
  reader_start = time.time()
  with WavReader(fn_r.name) as fr:
    logger.info(f"  Reader: channels={fr.channels}, samplerate={fr.samplerate}")
    with WavWriter(fn_w.name, fr.channels, fr.samplerate) as fw:
      logger.info(f"  Writer: channels={fr.channels}, samplerate={fr.samplerate}")
      logger.info(f"  Creating WSOLA processor... speed={coef}, frame_length=256, synthesis_hop={int(fr.samplerate / 70.0)}")
      
      tsm = wsola(channels = fr.channels, speed = coef, frame_length = 256, synthesis_hop = int(fr.samplerate / 70.0))
      logger.info(f"  Running WSOLA processing... (this may take a while)")
      
      wsola_start = time.time()
      tsm.run(fr, fw)
      wsola_elapsed = time.time() - wsola_start
      logger.info(f"  ✓ WSOLA completed in {wsola_elapsed:.2f}s")
  
  reader_elapsed = time.time() - reader_start
  logger.info(f"✓ WSOLA processing completed in {reader_elapsed:.2f}s")
  
  # Load and resample
  logger.info(f"Loading processed audio and resampling...")
  load_start = time.time()
  y_loaded, sr_loaded = librosa.load(fn_w.name)
  load_elapsed = time.time() - load_start
  logger.info(f"  ✓ Loaded in {load_elapsed:.2f}s - shape={y_loaded.shape}, sr={sr_loaded}")
  
  logger.info(f"Resampling to original length ({len(x)} samples)...")
  resample_start = time.time()
  y = resample(y_loaded, len(x)).astype(x.dtype)
  resample_elapsed = time.time() - resample_start
  logger.info(f"  ✓ Resampled in {resample_elapsed:.2f}s - output shape={y.shape}")
  
  # Cleanup
  logger.info(f"Closing temporary files...")
  fn_r.close()
  fn_w.close()
  
  total_elapsed = time.time() - total_start
  logger.info(f"--- resampling() END (total: {total_elapsed:.2f}s) ---")
  logger.info(f"Breakdown:")
  logger.info(f"  - Write input WAV: {write_elapsed:.2f}s")
  logger.info(f"  - WSOLA processing: {reader_elapsed:.2f}s (wsola.run: {wsola_elapsed:.2f}s)")
  logger.info(f"  - Load processed: {load_elapsed:.2f}s")
  logger.info(f"  - Resample: {resample_elapsed:.2f}s")

  return y

# Mcadams transformation: Baseline2 of VoicePrivacy2020
def vp_baseline2(x, mcadams = 0.8, winlen = int(20 * 0.001 * 16000), shift = int(10 * 0.001 * 16000), lp_order = 20):
  logger.info(f"vp_baseline2() called with mcadams={mcadams}, winlen={winlen}, shift={shift}, lp_order={lp_order}")
  start = time.time()
  
  eps = np.finfo(np.float32).eps
  x2 = copy.deepcopy(x) + eps
  length_x = len(x2)
  
  # FFT parameters
  # n_fft = 2**(np.ceil((np.log2(winlen)))).astype(int)
  wPR = np.hanning(winlen)
  K = np.sum(wPR)/shift
  win = np.sqrt(wPR/K)
  n_frame = 1+np.floor((length_x-winlen)/shift).astype(int) # nr of complete frames
  logger.info(f"Processing {n_frame} frames...")
  
  # carry out the overlap - add FFT processing
  y = np.zeros([length_x])

  for m in np.arange(1, n_frame):
    # indices of the mth frame
    index = np.arange(m*shift,np.minimum(m*shift+winlen,length_x))    
    # windowed mth frame (other than rectangular window)
    frame = x2[index]*win 
    # get lpc coefficients
    a_lpc = librosa.lpc(frame+eps, order=lp_order)
    # get poles
    poles = scipy.signal.tf2zpk(np.array([1]), a_lpc)[1]
    #index of imaginary poles
    ind_imag = np.where(np.isreal(poles)==False)[0]
    #index of first imaginary poles
    ind_imag_con = ind_imag[np.arange(0,np.size(ind_imag),2)]
    
    # here we define the new angles of the poles, shifted accordingly to the mcadams coefficient
    # values >1 expand the spectrum, while values <1 constract it for angles>1
    # values >1 constract the spectrum, while values <1 expand it for angles<1
    # the choice of this value is strongly linked to the number of lpc coefficients
    # a bigger lpc coefficients number constraints the effect of the coefficient to very small variations
    # a smaller lpc coefficients number allows for a bigger flexibility
    new_angles = np.angle(poles[ind_imag_con])**mcadams
    
    # make sure new angles stay between 0 and pi
    new_angles[np.where(new_angles>=np.pi)] = np.pi        
    new_angles[np.where(new_angles<=0)] = 0  
    
    # copy of the original poles to be adjusted with the new angles
    new_poles = poles
    for k in np.arange(np.size(ind_imag_con)):
      # compute new poles with the same magnitued and new angles
      new_poles[ind_imag_con[k]] = np.abs(poles[ind_imag_con[k]])*np.exp(1j*new_angles[k])
      # applied also to the conjugate pole
      new_poles[ind_imag_con[k]+1] = np.abs(poles[ind_imag_con[k]+1])*np.exp(-1j*new_angles[k])
        
    # recover new, modified lpc coefficients
    a_lpc_new = np.real(np.poly(new_poles))
    # get residual excitation for reconstruction
    res = lfilter(a_lpc,np.array(1),frame)
    # reconstruct frames with new lpc coefficient
    frame_rec = lfilter(np.array([1]),a_lpc_new,res)
    frame_rec = frame_rec*win    
    
    outindex = np.arange(m*shift,m*shift+len(frame_rec))
    # overlap add
    y[outindex] = y[outindex] + frame_rec
      
  y = y/np.max(np.abs(y))
  elapsed = time.time() - start
  logger.info(f"✓ vp_baseline2() completed in {elapsed:.2f}s")
  return y.astype(x.dtype)

def _trajectory_smoothing(x, thresh = 0.5):
  y = copy.copy(x)

  b, a = signal.butter(2, thresh)
  for d in range(y.shape[1]):
    y[:, d] = signal.filtfilt(b, a, y[:, d])
    y[:, d] = signal.filtfilt(b, a, y[::-1, d])[::-1]

  return y

# modulation spectrum smoothing
def modspec_smoothing(x, coef = 0.1):
  logger.info(f"modspec_smoothing() called with coef={coef}")
  start = time.time()
  
  # STFT
  mag_x, phase_x = rs.magphase(rs.core.stft(x))
  mag_x, phase_x = np.log(mag_x).T, phase_x.T
  mag_x_smoothed = _trajectory_smoothing(mag_x, coef)

  # ISTFT
  y = np.real(rs.core.istft(np.exp(mag_x_smoothed).T * phase_x.T)).astype(x.dtype)
  y = y * np.sqrt(np.sum(x * x)) / np.sqrt(np.sum(y * y))
  
  elapsed = time.time() - start
  logger.info(f"✓ modspec_smoothing() completed in {elapsed:.2f}s")
  return y

# waveform clipping
def clipping(x, thresh = 0.5):
  logger.info(f"clipping() called with thresh={thresh}")
  start = time.time()
  
  hist, bins = np.histogram(np.abs(x), 1000)
  hist = np.cumsum(hist)
  abs_thresh = bins[np.where(hist >= min(max(0., thresh), 1.) * np.amax(hist))[0][0]]

  y = np.clip(x, - abs_thresh, abs_thresh)
  y = y * np.divide(np.sqrt(np.sum(x * x)), np.sqrt(np.sum(y * y)), out=np.zeros_like(np.sqrt(np.sum(x * x))), where=np.sqrt(np.sum(y * y))!=0)

  elapsed = time.time() - start
  logger.info(f"✓ clipping() completed in {elapsed:.2f}s")
  return y

# chorus effect
def chorus(x, coef = 0.1):
  logger.info(f"chorus() called with coef={coef}")
  start = time.time()
  
  coef = max(0., coef)
  xp, xo, xm = vtln(x, coef), vtln(x, 0.), vtln(x, - coef)

  result = (xp + xo + xm) / 3.0
  elapsed = time.time() - start
  logger.info(f"✓ chorus() completed in {elapsed:.2f}s")
  return result
