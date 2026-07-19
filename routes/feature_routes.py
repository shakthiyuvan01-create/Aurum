"""Web routes for newly ported features — image gen, video gen, skills, TTS, scheduler."""
from __future__ import annotations

import json
import logging
import os

from flask import Blueprint, Response, jsonify, request, send_file

logger = logging.getLogger(__name__)

features_bp = Blueprint("features", __name__, url_prefix="/api/features")


# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------

@features_bp.route("/image/providers", methods=["GET"])
def list_image_providers():
    try:
        from image_gen.tool import list_available_providers
        return jsonify({"success": True, "providers": list_available_providers()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/image/generate", methods=["POST"])
def generate_image():
    try:
        data = request.get_json(force=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"success": False, "error": "Prompt is required"}), 400

        from image_gen.tool import generate_image as gen_img
        result = gen_img(
            prompt=prompt,
            provider=data.get("provider"),
            model=data.get("model"),
            aspect_ratio=data.get("aspect_ratio", "square"),
        )

        if result.get("success") and result.get("image"):
            img_path = result["image"]
            if os.path.exists(img_path):
                result["image_url"] = f"/uploads/{os.path.basename(img_path)}"
                result["serve_url"] = f"/api/features/image/file/{os.path.basename(img_path)}"

        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/image/file/<filename>", methods=["GET"])
def serve_image(filename):
    uploads = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    path = os.path.join(uploads, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return jsonify({"error": "File not found"}), 404


# ---------------------------------------------------------------------------
# Video Generation
# ---------------------------------------------------------------------------

@features_bp.route("/video/providers", methods=["GET"])
def list_video_providers():
    try:
        from video_gen.tool import list_video_providers
        return jsonify({"success": True, "providers": list_video_providers()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/video/generate", methods=["POST"])
def generate_video():
    try:
        data = request.get_json(force=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"success": False, "error": "Prompt is required"}), 400

        from video_gen.tool import generate_video as gen_vid
        result = gen_vid(
            prompt=prompt,
            provider=data.get("provider"),
            duration=data.get("duration", 5),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@features_bp.route("/skills", methods=["GET"])
def list_skills():
    try:
        from skills.skills_tool import list_skills, list_categories, refresh_skills
        category = request.args.get("category")
        all_skills = list_skills(category)
        cats = list_categories()
        return jsonify({
            "success": True,
            "skills": all_skills,
            "categories": cats,
            "total": len(all_skills),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/skills/refresh", methods=["POST"])
def refresh_skills():
    try:
        from skills.skills_tool import refresh_skills
        count = refresh_skills()
        return jsonify({"success": True, "skills_loaded": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/skills/run", methods=["POST"])
def run_skill():
    try:
        data = request.get_json(force=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"success": False, "error": "Skill name is required"}), 400

        from skills.skills_tool import run_skill
        params = {k: v for k, v in data.items() if k != "name"}
        result = run_skill(name, **params)
        return jsonify({"success": True, "name": name, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

@features_bp.route("/tts/providers", methods=["GET"])
def list_tts_providers():
    try:
        from tts.tool import list_tts_providers
        return jsonify({"success": True, "providers": list_tts_providers()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/tts/speak", methods=["POST"])
def text_to_speech():
    try:
        data = request.get_json(force=True) or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"success": False, "error": "Text is required"}), 400

        from tts.tool import text_to_speech as tts
        # First try the assistant's native say (always works on Windows)
        from assistant.speech import say
        say(text)
        return jsonify({"success": True, "text": text, "method": "native"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Scheduler / Cron
# ---------------------------------------------------------------------------

@features_bp.route("/scheduler/jobs", methods=["GET"])
def list_jobs():
    try:
        from cron.tool import list_scheduled_jobs
        return jsonify({"success": True, "jobs": list_scheduled_jobs()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/scheduler/schedule", methods=["POST"])
def schedule_job():
    try:
        data = request.get_json(force=True) or {}
        name = data.get("name", "untitled")
        job_type = data.get("type", "log")
        params = data.get("params", {})

        recurring = data.get("recurring", False)
        if recurring:
            interval = data.get("interval_minutes", 60)
            from cron.tool import schedule_recurring
            job_id = schedule_recurring(name, job_type, params, interval)
        else:
            delay = data.get("delay_minutes", 0)
            from cron.tool import schedule_once
            job_id = schedule_once(name, job_type, params, delay)

        return jsonify({"success": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@features_bp.route("/scheduler/cancel/<job_id>", methods=["DELETE"])
def cancel_job(job_id):
    try:
        from cron.tool import cancel_job
        if cancel_job(job_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Job not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

@features_bp.route("/status", methods=["GET"])
def features_status():
    """Report which feature systems are available."""
    status = {}
    try:
        from image_gen.tool import list_available_providers
        providers = list_available_providers()
        status["image_gen"] = {
            "available": any(p["available"] for p in providers),
            "providers": len(providers),
        }
    except Exception:
        status["image_gen"] = {"available": False, "error": "not loaded"}

    try:
        from video_gen.tool import list_video_providers
        vp = list_video_providers()
        status["video_gen"] = {
            "available": any(p["available"] for p in vp),
            "providers": len(vp),
        }
    except Exception:
        status["video_gen"] = {"available": False}

    try:
        from skills.skills_tool import list_skills
        sl = list_skills()
        status["skills"] = {"available": len(sl) > 0, "count": len(sl)}
    except Exception:
        status["skills"] = {"available": False}

    try:
        from cron.tool import list_scheduled_jobs
        status["scheduler"] = {"available": True}
    except Exception:
        status["scheduler"] = {"available": False}

    return jsonify({"success": True, "features": status})
