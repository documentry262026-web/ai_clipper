import os
import shutil
import streamlit as st
from moviepy.editor import VideoFileClip, CompositeAudioClip
import whisper
import yt_dlp
import numpy as np

st.set_page_config(page_title="AI Video Clipper Pro", page_icon="✂️", layout="centered")

st.title("🎬 Private AI Video Clipper Pro")
st.write("Upload or link any video (YouTube, Bilibili, etc.) with live download progress!")

def clean_storage():
    video_path = "temp_input_video.mp4"
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
        except:
            pass
    bgm_path = "temp_bgm.mp3"
    if os.path.exists(bgm_path):
        try:
            os.remove(bgm_path)
        except:
            pass
    output_dir = "output_clips"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

input_method = st.radio("Choose input method:", ("Upload Video File", "Paste Video Link (YouTube/Bilibili/Web)"))

video_path = "temp_input_video.mp4"

if input_method == "Upload Video File":
    uploaded_file = st.file_uploader("Choose a video file (MP4, MOV)", type=["mp4", "mov"])
    if uploaded_file is not None:
        if not os.path.exists(video_path):
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

else:
    url_input = st.text_input("Paste Full Video URL (e.g., Bilibili or YouTube link):")
    
    if st.button("📥 Download Video from Link"):
        if url_input:
            clean_storage() 
            
            # Streamlit placeholder for live download progress
            download_status = st.empty()
            download_bar = st.progress(0)
            
            def my_hook(d):
                if d['status'] == 'downloading':
                    try:
                        # Calculate percentage safely
                        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        downloaded_bytes = d.get('downloaded_bytes', 0)
                        if total_bytes > 0:
                            percent = int(downloaded_bytes / total_bytes * 100)
                            download_bar.progress(min(percent, 100))
                            download_status.text(f"📥 Downloading... {percent}% done ({downloaded_bytes / 1024 / 1024:.1f} MB)")
                        else:
                            download_status.text(f"📥 Downloading... ({downloaded_bytes / 1024 / 1024:.1f} MB downloaded)")
                    except Exception:
                        pass
                elif d['status'] == 'finished':
                    download_bar.progress(100)
                    download_status.text("⚙️ Download finished! Merging video & audio...")

            try:
                ydl_opts = {
                    'format': 'bv*+ba/b',
                    'outtmpl': video_path,
                    'overwrites': True,
                    'noplaylist': True,
                    'merge_output_format': 'mp4',
                    'socket_timeout': 30,
                    'retries': 15,
                    'fragment_retries': 15,
                    'progress_hooks': [my_hook],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url_input])
                st.success("Video downloaded successfully!")
            except Exception as e:
                st.error(f"Download failed: {e}")
        else:
            st.warning("Please paste a valid video URL first!")

if os.path.exists(video_path):
    st.video(video_path)
    
    clip_length = st.slider("Select length of each clip (seconds):", min_value=15, max_value=60, value=30)
    
    flip_video = st.checkbox("Mirror/Flip Video Horizontally", value=False)
    add_bgm = st.checkbox("Add Copyright-Free Background Music (20% Volume)", value=True)
    
    if st.button("🚀 Generate Short Clips"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔄 Loading Whisper AI model...")
        progress_bar.progress(10)
        model = whisper.load_model("base")
        
        status_text.text("🎙️ Transcribing audio segments...")
        progress_bar.progress(30)
        result = model.transcribe(video_path)
        
        status_text.text("✂️ Processing and cutting clips into 9:16 vertical shorts...")
        progress_bar.progress(60)
        
        output_dir = os.path.abspath("output_clips")
        os.makedirs(output_dir, exist_ok=True)
        
        video = VideoFileClip(video_path)
        total_duration = video.duration
        
        bgm_clip = None
        if add_bgm:
            try:
                bgm_duration = total_duration
                sample_rate = 44100
                t = np.linspace(0, bgm_duration, int(sample_rate * bgm_duration), endpoint=False)
                audio_data = 0.05 * np.sin(2 * np.pi * 220 * t) * np.exp(-t/bgm_duration)
                audio_array = np.int16(audio_data * 32767)
                stereo_array = np.column_stack((audio_array, audio_array))
                from moviepy.editor import AudioArrayClip
                bgm_clip = AudioArrayClip(stereo_array, fps=sample_rate).volumetrically(0.2)
            except Exception:
                pass

        clips_data = []
        current_start = 0
        clip_counter = 1
        
        while current_start < total_duration:
            end_time = min(current_start + clip_length, total_duration)
            output_filename = os.path.join(output_dir, f"clip_{clip_counter}.mp4")
            
            subclip = video.subclip(current_start, end_time)
            
            w, h = subclip.size
            if w > h: 
                target_w = int(h * (9 / 16))
                x_center = w / 2
                subclip = subclip.crop(x1=x_center - target_w/2, x2=x_center + target_w/2, y1=0, y2=h)
            
            if flip_video:
                subclip = subclip.fx(lambda c: c.fl_image(lambda img: np.fliplr(img)))
                
            if add_bgm and bgm_clip:
                try:
                    sub_bgm = bgm_clip.subclip(0, subclip.duration)
                    if subclip.audio is not None:
                        mixed_audio = CompositeAudioClip([subclip.audio.volumetrically(0.9), sub_bgm])
                    else:
                        mixed_audio = sub_bgm
                    subclip = subclip.set_audio(mixed_audio)
                except Exception:
                    pass
            
            subclip.write_videofile(output_filename, codec="libx264", audio_codec="aac", logger=None)
            clips_data.append(output_filename)
            
            current_start += clip_length
            clip_counter += 1
            
        video.close()
        if bgm_clip:
            bgm_clip.close()
            
        progress_bar.progress(100)
        status_text.text("✅ All clips successfully generated!")
        
        st.success("Here are your generated 9:16 vertical shorts:")
        for clip_file in clips_data:
            st.video(clip_file)
            with open(clip_file, "rb") as f:
                st.download_button(
                    label=f"Download {os.path.basename(clip_file)}",
                    data=f,
                    file_name=os.path.basename(clip_file),
                    mime="video/mp4"
                )
