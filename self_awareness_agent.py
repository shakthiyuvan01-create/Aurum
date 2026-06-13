from project_manager import project_stats
from memory_agent import analyze_memory


def self_awareness():

    stats = project_stats()

    memory = analyze_memory()

    return {
        "project": stats,
        "memory": memory
    }