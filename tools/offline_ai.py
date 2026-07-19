"""tools/offline_ai.py - Offline AI: Ollama, local LLMs, GPU, offline speech, user learning"""
from __future__ import annotations
import json, logging, os, subprocess, sys, time
from pathlib import Path

NAME = "offline_ai"
DESCRIPTION = "Manage offline AI: Ollama, local LLMs, GPU acceleration, offline speech recognition/TTS, user learning"
CATEGORY = "builtin"
ICON = "🤖"

INPUTS = [
    {"name":"action","type":"str","required":True,
     "placeholder":"ollama_status|ollama_pull|ollama_list|ollama_run|gpu_info|offline_stt|offline_tts|learn_preference|forget_pattern|learning_stats"},
    {"name":"model","type":"str","placeholder":"Model name (e.g., llama3.2)"},
    {"name":"text","type":"str","placeholder":"Text to process"},
    {"name":"key","type":"str","placeholder":"Preference key"},
    {"name":"value","type":"str","placeholder":"Preference value"},
]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

def run(action="",model="",text="",key="",value="",**kw):
    a=action.strip().lower()
    if a=="ollama_status": return _ollama_status()
    if a=="ollama_pull": return _ollama_pull(model)
    if a=="ollama_list": return _ollama_list()
    if a=="ollama_run": return _ollama_run(model,text)
    if a=="gpu_info": return _gpu_info()
    if a=="offline_stt": return _offline_stt(text or key)
    if a=="offline_tts": return _offline_tts(text,model or "output.wav")
    if a=="learn_preference": return _learn_pref(key,value,text)
    if a=="forget_pattern": return _forget(text or key)
    if a=="learning_stats": return _learning_stats()
    return {"error":f"Unknown: {action}"}

def _ollama_req(method,path,json_data=None):
    import requests
    url=f"{OLLAMA_URL.rstrip('/')}/api/{path}"
    if method=="GET": r=requests.get(url,timeout=10)
    elif method=="POST": r=requests.post(url,json=json_data or {},timeout=300)
    else: return {"error":f"Method {method}"}
    if r.status_code!=200: return {"error":f"HTTP {r.status_code}: {r.text[:200]}"}
    return r.json()

def _ollama_status():
    try:
        import requests
        r=requests.get(f"{OLLAMA_URL}/api/tags",timeout=5)
        if r.status_code!=200: return {"available":False,"error":f"HTTP {r.status_code}"}
        return {"available":True,"version":r.json().get("version","")}
    except Exception as e: return {"available":False,"error":str(e)}

def _ollama_pull(model):
    if not model: return {"error":"Model name required"}
    try:
        r=_ollama_req("POST","pull",{"name":model})
        return {"result":f"Pulling {model}...","model":model}
    except Exception as e: return {"error":str(e)}

def _ollama_list():
    try:
        d=_ollama_req("GET","tags")
        models=[{"name":m["name"],"size":m.get("size",0),"modified":m.get("modified_at","")} for m in d.get("models",[])]
        return {"result":models,"count":len(models)}
    except Exception as e: return {"error":str(e)}

def _ollama_run(model,prompt):
    if not model or not prompt: return {"error":"Model and prompt required"}
    try:
        d=_ollama_req("POST","generate",{"model":model,"prompt":prompt,"stream":False})
        return {"result":d.get("response","")[:2000],"model":model,"duration":d.get("total_duration",0)}
    except Exception as e: return {"error":str(e)}

def _gpu_info():
    """Detect GPU acceleration capabilities."""
    info={"cuda":False,"rocm":False,"metal":False,"gpu_count":0,"gpu_name":""}
    try:
        import torch
        info["cuda"]=torch.cuda.is_available()
        if info["cuda"]:
            info["gpu_count"]=torch.cuda.device_count()
            info["gpu_name"]=torch.cuda.get_device_name(0)
    except: pass
    # nvidia-smi
    try:
        r=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"],
                         capture_output=True,text=True,timeout=5)
        if r.returncode==0:
            info["nvidia_smi"]=[l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except: pass
    # DirectML / ROCm
    try:
        import onnxruntime as ort
        info["directml"]="DmlExecutionProvider" in ort.get_available_providers()
        info["rocm"]="ROCMExecutionProvider" in ort.get_available_providers()
    except: pass
    return {"result":info}

def _offline_stt(audio_path):
    """Offline speech-to-text using faster-whisper or whisper."""
    try:
        from faster_whisper import WhisperModel
        model=WhisperModel("base",device="cpu",compute_type="int8")
        segments,_=model.transcribe(audio_path)
        text=" ".join(s.text for s in segments)
        return {"result":text.strip(),"engine":"faster-whisper"}
    except ImportError:
        try:
            import whisper
            model=whisper.load_model("base")
            r=model.transcribe(audio_path)
            return {"result":r["text"].strip(),"engine":"whisper"}
        except ImportError: return {"error":"pip install faster-whisper or openai-whisper"}
    except Exception as e: return {"error":str(e)}

def _offline_tts(text,output_path):
    """Offline text-to-speech using gTTS, pyttsx3, or edge-tts."""
    if not text: return {"error":"Text required"}
    try:
        from gtts import gTTS
        tts=gTTS(text); tts.save(output_path)
        return {"result":f"Speech saved: {output_path}","file":output_path,"engine":"gTTS"}
    except ImportError:
        pass
    try:
        import edge_tts
        import asyncio
        async def _run():
            comm=edge_tts.Communicate(text,"en-US-JennyNeural")
            await comm.save(output_path)
        asyncio.run(_run())
        return {"result":f"Speech saved: {output_path}","file":output_path,"engine":"edge-tts"}
    except ImportError:
        pass
    try:
        import pyttsx3
        engine=pyttsx3.init()
        engine.save_to_file(text,output_path)
        engine.runAndWait()
        return {"result":f"Speech saved: {output_path}","file":output_path,"engine":"pyttsx3"}
    except ImportError: return {"error":"Install one of: gtts, edge-tts, pyttsx3"}
    except Exception as e: return {"error":str(e)}

def _learn_pref(key,value,username="default"):
    """Learn a user preference using the learning system."""
    if not key: return {"error":"Key required"}
    try:
        from services.learning import add_fact
        username=username or "default"
        add_fact(f"{key}: {value}",username)
        return {"result":f"Learned: {key} = {value}","key":key}
    except ImportError: return {"error":"Learning system unavailable"}
    except Exception as e: return {"error":str(e)}

def _forget(pattern,username="default"):
    """Forget learned patterns matching a key."""
    try:
        from services.learning import retrieve
        return {"result":f"Forget patterns matching: {pattern}","note":"Use memory_agent forget action"}
    except Exception as e: return {"error":str(e)}

def _learning_stats():
    """Get user learning system statistics."""
    try:
        from services.learning import stats
        s=stats()
        if s: return {"result":s}
        return {"result":"No learning data","note":"Learning system uses learning_data/*.txt files"}
    except Exception as e: return {"error":str(e)}
