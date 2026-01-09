# Audio Anonymizer - Deployment Guide

## Language Support

The application now supports **Luganda** and **English** surrogate audio files.

### Directory Structure

Place your surrogate audio files in the following structure:

```
data/surrogates/
├── luganda/
│   ├── male/
│   │   ├── person/
│   │   ├── user_id/
│   │   └── location/
│   └── female/
│       ├── person/
│       ├── user_id/
│       └── location/
└── english/
    ├── male/
    │   ├── person/
    │   ├── user_id/
    │   └── location/
    └── female/
        ├── person/
        ├── user_id/
        └── location/
```

### Fallback Order

The system searches for surrogates in this priority:
1. `<language>/<gender>/<label>/` (most specific - e.g., luganda/male/person/)
2. `<language>/<label>/<gender>/` (alternative ordering)
3. `<language>/<label>/` (language + label, any gender)
4. `<language>/<gender>/` (language + gender only)
5. `<gender>/<label>/` (gender + label, any language)
6. `<gender>/` (gender only, any language)

**Note**: If no surrogate is found, a placeholder tone is generated. Always ensure surrogates exist for your use cases.

---

## 🐳 Docker Deployment

### Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (included with Docker Desktop)

### Quick Start

1. **Build and run** with docker-compose:
   ```bash
   docker-compose up -d
   ```

2. **Access the app** at:
   - Local: http://localhost:7860
   - Network: http://YOUR_SERVER_IP:7860

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Stop the app**:
   ```bash
   docker-compose down
   ```

### Manual Docker Build

```bash
# Build the image
docker build -t audio-anonymizer .

# Run the container
docker run -d \
  -p 7860:7860 \
  -v $(pwd)/data/surrogates:/app/data/surrogates:ro \
  -v $(pwd)/output:/app/output \
  --name audio-anonymizer \
  audio-anonymizer
```

---

## ☁️ Cloud Deployment Options

### Option 1: Hugging Face Spaces (Recommended for Gradio)

1. Create a new Space on [Hugging Face](https://huggingface.co/spaces)
2. Choose **Gradio** as the SDK
3. Upload your files:
   - `app/gradio_app.py` → `app.py` (rename)
   - `backend/` folder
   - `requirements.txt`
   - `data/surrogates/` folder
4. Set Space to **Public** or **Private**
5. Gradio automatically handles HTTPS and downloads

**Benefits:**
- Free hosting for public apps
- Automatic HTTPS
- Built-in authentication (for private spaces)
- No server management

### Option 2: AWS/GCP/Azure with Docker

1. **Push image to registry**:
   ```bash
   docker tag audio-anonymizer YOUR_REGISTRY/audio-anonymizer:latest
   docker push YOUR_REGISTRY/audio-anonymizer:latest
   ```

2. **Deploy to cloud**:
   - **AWS ECS/Fargate**: Use task definitions with port 7860
   - **Google Cloud Run**: Deploy container with port mapping
   - **Azure Container Instances**: Deploy with public IP

3. **Configure**:
   - Expose port 7860
   - Mount persistent volumes for `output/`
   - Set environment variables for HTTPS

### Option 3: VPS/Dedicated Server

1. **Install Docker** on your server
2. **Clone repository**:
   ```bash
   git clone YOUR_REPO
   cd audio_anony
   ```
3. **Run with docker-compose**:
   ```bash
   docker-compose up -d
   ```
4. **Set up reverse proxy** (Nginx/Caddy) for HTTPS:
   ```nginx
   server {
       listen 443 ssl;
       server_name your-domain.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://localhost:7860;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
       }
   }
   ```

---

## 📥 Download Mechanism

### Local Development
- Files are saved to `output/` directory with timestamps
- Access via filesystem

### Deployed (HTTP/HTTPS)
- Gradio's Audio component automatically provides a **download button** (⬇)
- Click the download icon on the output audio player
- Browser downloads the file directly
- Works seamlessly on both HTTP and HTTPS

**No additional code needed!** Gradio handles downloads automatically.

---

## 🔒 Security Considerations

### For Production:

1. **Authentication**:
   ```python
   # In gradio_app.py
   demo.launch(auth=("username", "password"))
   ```

2. **HTTPS**:
   - Use reverse proxy (Nginx/Caddy)
   - Or deploy to platform with automatic HTTPS (Hugging Face, Cloud Run)

3. **File Size Limits**:
   ```python
   # In gradio_app.py
   audio_in = gr.Audio(
       type="filepath",
       label="Upload or Record Audio",
       max_length=300  # 5 minutes max
   )
   ```

4. **Rate Limiting**:
   - Use Nginx `limit_req` module
   - Or cloud provider rate limiting

---

## 🧪 Testing Deployment

1. **Local test**:
   ```bash
   python3 app/gradio_app.py
   ```

2. **Docker test**:
   ```bash
   docker-compose up
   ```

3. **Verify**:
   - Upload audio file
   - Add annotations with language selection
   - Click "Anonymize Audio"
   - Download output using ⬇ button

---

## 📊 Monitoring

### Docker Logs
```bash
docker-compose logs -f
```

### Resource Usage
```bash
docker stats audio-anonymizer
```

### Health Check
Add to `docker-compose.yml`:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:7860"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## 🚀 Performance Tips

1. **Surrogate file organization**:
   - Use compressed formats (MP3 @ 128kbps) for smaller file sizes
   - Keep surrogate files under 5 seconds for faster processing

2. **Container resources**:
   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
   ```

3. **Caching**:
   - Surrogates are read from disk each time
   - Consider adding caching for frequently used surrogates (future enhancement)

---

## 📝 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADIO_SERVER_NAME` | `0.0.0.0` | Server bind address |
| `GRADIO_SERVER_PORT` | `7860` | Server port |

---

## 🐛 Troubleshooting

### Issue: Can't download files in deployed app
**Solution**: Files are automatically downloadable via Gradio's built-in download button. No action needed.

### Issue: Surrogate files not found
**Solution**: Check directory structure matches `<language>/<gender>/<label>/`

### Issue: Container won't start
**Solution**: Check logs with `docker-compose logs`

### Issue: Out of memory
**Solution**: Increase container memory limits or use smaller audio files

---

## 📚 Additional Resources

- [Gradio Documentation](https://gradio.app/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces)
