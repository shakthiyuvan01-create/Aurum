"""tools/media.py - Video & Audio: generate, edit, subtitles, screen record, music, voice cloning"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

NAME = "media"
DESCRIPTION = "Generate/edit videos, audio, subtitles, screen recording, music, voice cloning, podcast creation"
CATEGORY = "builtin"
ICON = "🎬"
BASE = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE / "media"
MEDIA_DIR.mkdir(exist_ok=True)

INPUTS = [
    {"name":"action","type":"str","required":True,"placeholder":"generate_video|edit_video|create_subtitles|lip_sync|screen_record|generate_music|sound_effects|voice_clone|create_podcast|audio_enhance"},
    {"name":"input_path","type":"str","placeholder":"Input file path"},
    {"name":"output_path","type":"str","placeholder":"Output file path"},
    {"name":"text","type":"str","placeholder":"Text content / script"},
    {"name":"params","type":"str","placeholder":"JSON parameters"},
]

def run(action="",input_path="",output_path="",text="",params="",**kw):
    a=action.strip().lower(); out=output_path or str(MEDIA_DIR/f"{a}_{int(time.time())}")
    p=json.loads(params) if params else {}
    if a=="generate_video": return _gen_video(text or p.get("prompt",""),out,p)
    if a=="edit_video": return _edit_vid(input_path,out,p)
    if a=="create_subtitles": return _subs(input_path or text,out)
    if a=="lip_sync": return _lip_sync(input_path,text or p.get("audio",""),out)
    if a=="screen_record": return _screen_record(out,p.get("duration",10),p)
    if a=="generate_music": return _music(text or p.get("prompt",""),out)
    if a=="sound_effects": return _sfx(text or p.get("prompt",""),out)
    if a=="voice_clone": return _voice_clone(input_path,text or p.get("text",""),out)
    if a=="create_podcast": return _podcast(text or p.get("script",""),out,p)
    if a=="audio_enhance": return _enhance(input_path,out)
    return {"error":f"Unknown: {action}"}

def _check_ffmpeg():
    try: subprocess.run(["ffmpeg","-version"],capture_output=True,timeout=5); return True
    except: return False

def _gen_video(prompt,output,params):
    """Generate video using AI video providers."""
    try:
        from image_gen.tool import generate_video as _gv
        r=_gv(prompt,aspect_ratio=params.get("aspect_ratio","16:9"))
        if r.get("success") and r.get("video"): return {"result":r["video"],"format":"video"}
    except: pass
    # fallback: use ffmpeg to create a slideshow
    if not _check_ffmpeg(): return {"error":"pip install image_gen tools or ffmpeg"}
    try:
        import requests
        img=requests.get(f"https://image.pollinations.ai/prompt/{prompt}",timeout=30)
        img_path=MEDIA_DIR/"frame.png"; img_path.write_bytes(img.content)
        r=subprocess.run(["ffmpeg","-loop","1","-i",str(img_path),"-c:v","libx264","-t","5","-pix_fmt","yuv420p",output,"-y"],
                         capture_output=True,text=True,timeout=30)
        return {"result":output if r.returncode==0 else r.stderr[:200]}
    except Exception as e: return {"error":str(e)}

def _edit_vid(input_path,output,params):
    if not _check_ffmpeg(): return {"error":"ffmpeg required"}
    try:
        cmd=["ffmpeg","-i",input_path]
        if params.get("trim_start"): cmd.extend(["-ss",str(params["trim_start"])])
        if params.get("trim_end"): cmd.extend(["-to",str(params["trim_end"])])
        if params.get("width") and params.get("height"): cmd.extend(["-vf",f"scale={params['width']}:{params['height']}"])
        cmd.extend([output,"-y"])
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        return {"result":output if r.returncode==0 else r.stderr[:200]}
    except Exception as e: return {"error":str(e)}

def _subs(input_text,output):
    """Create subtitle file from text."""
    if os.path.isfile(input_text):
        with open(input_text) as f: text=f.read()
    else: text=input_text
    lines=text.strip().split("\n")
    srt=[]
    for i,line in enumerate(lines):
        if not line.strip(): continue
        start=i*3; end=(i+1)*3
        srt.append(f"{i+1}\n{start:02d}:00:00,000 --> {end:02d}:00:00,000\n{line}\n")
    srt_path=output if output.endswith(".srt") else output+".srt"
    with open(srt_path,"w",encoding="utf-8") as f: f.write("\n".join(srt))
    return {"result":f"Subtitles created: {srt_path}","file":srt_path,"lines":len(lines)}

def _lip_sync(video,audio,output):
    if not _check_ffmpeg(): return {"error":"ffmpeg required"}
    try:
        r=subprocess.run(["ffmpeg","-i",video,"-i",audio,"-c:v","copy","-c:a","aac",output,"-y"],
                         capture_output=True,text=True,timeout=120)
        return {"result":output if r.returncode==0 else r.stderr[:200]}
    except Exception as e: return {"error":str(e)}

def _screen_record(output,duration=10,params=None):
    """Record screen using platform-specific tools."""
    try:
        if sys.platform=="win32":
            # Use windows screen capture via pyautogui
            import pyautogui
            import cv2, numpy as np
            frames=[]
            for i in range(min(duration*4,100)):
                img=pyautogui.screenshot()
                frames.append(np.array(img))
                time.sleep(0.25)
            if frames:
                h,w,_=frames[0].shape
                fourcc=cv2.VideoWriter_fourcc(*"mp4v")
                out=cv2.VideoWriter(output,fourcc,4.0,(w,h))
                for f in frames: out.write(cv2.cvtColor(f,cv2.COLOR_RGB2BGR))
                out.release()
                return {"result":f"Recording saved: {output}","file":output,"frames":len(frames)}
            return {"error":"No frames captured"}
        else:
            if not _check_ffmpeg(): return {"error":"ffmpeg required"}
            r=subprocess.run(["ffmpeg","-f","x11grab","-video_size","1920x1080","-i",":0.0","-t",str(duration),output,"-y"],
                             capture_output=True,text=True,timeout=duration+30)
            return {"result":output if r.returncode==0 else r.stderr[:200]}
    except ImportError: return {"error":"pip install opencv-python pyautogui numpy"}
    except Exception as e: return {"error":str(e)}

def _music(prompt,output):
    """Generate music using AI providers."""
    try:
        from providers import AI
        r=AI.generate(f"Write a short music description based on: {prompt}. Output a JSON with genre,tempo,instruments.",max_tokens=300)
        return {"result":f"Music concept created for '{prompt}'","prompt":prompt,"analysis":(r or "")[:500],
                "note":"Use Suno AI, MusicGen, or similar via API for actual audio. Install via plugins/mcp."}
    except Exception as e: return {"error":str(e)}

def _sfx(prompt,output):
    return {"result":f"Sound effect concept: {prompt}","note":"Connect to SFX APIs via MCP or plugins"}

def _voice_clone(audio_input,text,output):
    """Voice cloning requires ElevenLabs or similar."""
    api_key=os.getenv("ELEVENLABS_API_KEY","")
    if not api_key: return {"error":"Set ELEVENLABS_API_KEY in .env for voice cloning"}
    try:
        import requests
        # Get voices
        r=requests.get("https://api.elevenlabs.io/v1/voices",headers={"xi-api-key":api_key})
        voices=r.json().get("voices",[]); default_id=voices[0]["voice_id"] if voices else ""
        resp=requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{default_id}",
                          headers={"xi-api-key":api_key,"Content-Type":"application/json"},
                          json={"text":text or "Hello, this is a voice clone.","model_id":"eleven_monolingual_v1"},
                          timeout=60)
        if resp.status_code==200:
            with open(output+".mp3","wb") as f: f.write(resp.content)
            return {"result":f"Audio generated: {output}.mp3","file":output+".mp3"}
        return {"error":f"API error: {resp.status_code}"}
    except Exception as e: return {"error":str(e)}

def _podcast(script,output,params):
    """Create a podcast script and optionally generate audio."""
    lines=script.strip().split("\n")
    script_path=output+".md" if not output.endswith(".md") else output
    with open(script_path,"w",encoding="utf-8") as f:
        f.write(f"# Podcast\n\n{script}\n\n---\nGenerated by Aurum Media")
    return {"result":f"Podcast script saved: {script_path}","file":script_path,"segments":len(lines)}

def _enhance(input_path,output):
    """Basic audio enhancement using ffmpeg."""
    if not _check_ffmpeg(): return {"error":"ffmpeg required"}
    try:
        r=subprocess.run(["ffmpeg","-i",input_path,"-af","volume=1.5,highpass=f=200,lowpass=f=3000",
                         output,"-y"],capture_output=True,text=True,timeout=60)
        return {"result":output if r.returncode==0 else r.stderr[:200],"enhanced":True}
    except Exception as e: return {"error":str(e)}
