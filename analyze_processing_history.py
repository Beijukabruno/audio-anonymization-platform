#!/usr/bin/env python3
"""
Analysis script for audio anonymization platform processing history
"""
import pandas as pd
import numpy as np
from datetime import datetime
import sys

# Load the CSV
csv_path = "/home/beijuka/Downloads/processing_history_20260208_115516.csv"

try:
    df = pd.read_csv(csv_path)
    print("="*80)
    print("AUDIO ANONYMIZATION PLATFORM - PROCESSING HISTORY ANALYSIS")
    print("="*80)
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Records: {len(df)}")
    print("="*80)
    
    # 1. STATUS BREAKDOWN
    print("\n📊 1. PROCESSING STATUS OVERVIEW")
    print("-" * 50)
    status_counts = df['Status'].value_counts()
    for status, count in status_counts.items():
        percentage = (count / len(df)) * 100
        print(f"   {status.upper():12s}: {count:3d} records ({percentage:5.1f}%)")
    
    # 2. GENDER DISTRIBUTION
    print("\n👥 2. GENDER DISTRIBUTION")
    print("-" * 50)
    gender_counts = df['Gender'].value_counts()
    for gender, count in gender_counts.items():
        percentage = (count / len(df)) * 100
        print(f"   {gender.capitalize():12s}: {count:3d} records ({percentage:5.1f}%)")
    
    # 3. SURROGATE ASSIGNMENT ANALYSIS
    print("\n🎭 3. SURROGATE ASSIGNMENT ANALYSIS")
    print("-" * 50)
    
    # Count entries with surrogates
    has_surrogate = df['Surrogate'].notna() & (df['Surrogate'] != '')
    surrogate_count = has_surrogate.sum()
    no_surrogate_count = len(df) - surrogate_count
    
    print(f"   With Surrogate : {surrogate_count:3d} records ({(surrogate_count/len(df))*100:5.1f}%)")
    print(f"   No Surrogate   : {no_surrogate_count:3d} records ({(no_surrogate_count/len(df))*100:5.1f}%)")
    
    # Surrogate type breakdown
    if surrogate_count > 0:
        print("\n   Surrogate Type Distribution:")
        surrogate_types = df[has_surrogate]['Surrogate'].apply(lambda x: x.split('_')[-1] if pd.notna(x) else None)
        surrogate_type_counts = surrogate_types.value_counts()
        for stype, count in surrogate_type_counts.items():
            print(f"      {stype:12s}: {count:3d} ({(count/surrogate_count)*100:5.1f}% of surrogates)")
    
    # Gender mismatch analysis
    print("\n   🔄 Gender-Surrogate Mismatches:")
    completed_df = df[df['Status'] == 'completed'].copy()
    
    # Extract surrogate gender (english_GENDER_type_TAG pattern)
    completed_df['surrogate_gender'] = completed_df['Surrogate'].apply(
        lambda x: x.split('_')[1] if pd.notna(x) and len(x.split('_')) >= 2 else None
    )
    
    mismatches = completed_df[
        (completed_df['surrogate_gender'].notna()) & 
        (completed_df['Gender'] != completed_df['surrogate_gender'])
    ]
    
    print(f"      Total Mismatches: {len(mismatches)} ({(len(mismatches)/len(completed_df))*100:.1f}% of completed)")
    
    if len(mismatches) > 0:
        print(f"\n      Examples:")
        for idx, row in mismatches.head(5).iterrows():
            print(f"         • {row['Filename'][:25]:25s} | Input: {row['Gender']:6s} → Surrogate: {row['surrogate_gender']:6s}")
    
    # 4. PROCESSING TIME ANALYSIS
    print("\n⏱️  4. PROCESSING PERFORMANCE")
    print("-" * 50)
    
    completed_with_time = df[(df['Status'] == 'completed') & (df['Duration (s)'].notna())]
    
    if len(completed_with_time) > 0:
        durations = completed_with_time['Duration (s)']
        print(f"   Completed Jobs : {len(completed_with_time)}")
        print(f"   Average Time   : {durations.mean():.2f} seconds")
        print(f"   Median Time    : {durations.median():.2f} seconds")
        print(f"   Min Time       : {durations.min():.2f} seconds")
        print(f"   Max Time       : {durations.max():.2f} seconds")
        print(f"   Std Deviation  : {durations.std():.2f} seconds")
        
        # Processing time by file size quartiles
        print("\n   Processing Time by File Size:")
        completed_with_time['size_quartile'] = pd.qcut(completed_with_time['Size (KB)'], 
                                                         q=4, 
                                                         labels=['Smallest 25%', 'Small-Med 25%', 'Med-Large 25%', 'Largest 25%'])
        quartile_stats = completed_with_time.groupby('size_quartile')['Duration (s)'].agg(['mean', 'median', 'count'])
        for quartile, row in quartile_stats.iterrows():
            print(f"      {quartile:15s}: Avg={row['mean']:6.2f}s, Median={row['median']:6.2f}s (n={int(row['count'])})")
    
    # 5. FILE SIZE ANALYSIS
    print("\n💾 5. FILE SIZE STATISTICS")
    print("-" * 50)
    
    file_sizes = df['Size (KB)'].dropna()
    if len(file_sizes) > 0:
        print(f"   Average Size   : {file_sizes.mean():8.1f} KB ({file_sizes.mean()/1024:.1f} MB)")
        print(f"   Median Size    : {file_sizes.median():8.1f} KB ({file_sizes.median()/1024:.1f} MB)")
        print(f"   Min Size       : {file_sizes.min():8.1f} KB")
        print(f"   Max Size       : {file_sizes.max():8.1f} KB ({file_sizes.max()/1024:.1f} MB)")
        print(f"   Total Volume   : {file_sizes.sum()/1024:.1f} MB ({file_sizes.sum()/1024/1024:.2f} GB)")
    
    # 6. STUCK/PROCESSING JOBS
    print("\n⚠️  6. STUCK PROCESSING JOBS (Requires Attention)")
    print("-" * 50)
    
    stuck_jobs = df[df['Status'] == 'processing']
    if len(stuck_jobs) > 0:
        print(f"   Found {len(stuck_jobs)} jobs stuck in 'processing' state:")
        for idx, row in stuck_jobs.iterrows():
            created_date = row['Created']
            print(f"      ID {row['ID']:3d} | {row['Filename']:40s} | Created: {created_date}")
    else:
        print("   ✅ No stuck jobs found!")
    
    # 7. PROCESSING TIMELINE
    print("\n📅 7. PROCESSING TIMELINE")
    print("-" * 50)
    
    completed_df = df[df['Status'] == 'completed'].copy()
    if len(completed_df) > 0:
        completed_df['date'] = pd.to_datetime(df['Created']).dt.date
        daily_counts = completed_df.groupby('date').size().sort_index()
        
        print(f"   Date Range     : {daily_counts.index.min()} to {daily_counts.index.max()}")
        print(f"   Total Days     : {len(daily_counts)} days")
        print(f"   Avg/Day        : {daily_counts.mean():.1f} files")
        print(f"   Busiest Day    : {daily_counts.index[daily_counts.argmax()]} ({daily_counts.max()} files)")
        
        print("\n   Recent Activity (Last 5 days):")
        for date, count in daily_counts.tail().items():
            print(f"      {date}: {count:3d} files")
    
    # 8. MOST PROCESSED FILES
    print("\n🔁 8. FREQUENTLY PROCESSED FILES")
    print("-" * 50)
    
    file_counts = df['Filename'].value_counts().head(10)
    print(f"   Top 10 files by processing attempts:")
    for filename, count in file_counts.items():
        print(f"      {count:2d}x | {filename}")
    
    # 9. ERROR ANALYSIS
    print("\n❌ 9. ERROR TRACKING")
    print("-" * 50)
    
    has_errors = df['Error'].notna() & (df['Error'] != '')
    error_count = has_errors.sum()
    
    if error_count > 0:
        print(f"   Records with Errors: {error_count}")
        print("\n   Error Messages:")
        for idx, row in df[has_errors].iterrows():
            print(f"      ID {row['ID']:3d} | {row['Filename'][:40]:40s}")
            print(f"              Error: {row['Error']}")
    else:
        print("   ✅ No errors recorded!")
    
    # 10. RECOMMENDATIONS
    print("\n💡 10. RECOMMENDATIONS")
    print("-" * 50)
    
    recommendations = []
    
    if len(stuck_jobs) > 0:
        recommendations.append(f"⚠️  Clear {len(stuck_jobs)} stuck 'processing' jobs (IDs: {', '.join(map(str, stuck_jobs['ID'].tolist()))})")
    
    if len(mismatches) > 0:
        recommendations.append(f"🔄 Review {len(mismatches)} gender-surrogate mismatches for consistency")
    
    if no_surrogate_count > 0:
        recommendations.append(f"🎭 {no_surrogate_count} records missing surrogate assignments")
    
    # Check for re-processed files
    duplicate_files = df['Filename'].value_counts()
    frequent_reprocessing = duplicate_files[duplicate_files > 5]
    if len(frequent_reprocessing) > 0:
        recommendations.append(f"🔁 {len(frequent_reprocessing)} files processed 5+ times (investigate why)")
    
    # Check processing efficiency
    if len(completed_with_time) > 0:
        slow_jobs = completed_with_time[completed_with_time['Duration (s)'] > 15]
        if len(slow_jobs) > 0:
            recommendations.append(f"⏱️  {len(slow_jobs)} jobs took >15s (consider optimization for large files)")
    
    if len(recommendations) > 0:
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    else:
        print("   ✅ System operating normally - no critical issues detected!")
    
    print("\n" + "="*80)
    print("END OF REPORT")
    print("="*80)

except FileNotFoundError:
    print(f"❌ Error: Could not find CSV file at {csv_path}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error analyzing data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
