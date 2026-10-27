from dataclasses import dataclass


@dataclass
class Scene:
    scene_id: int
    narration: str
    image_prompt: str
    duration: float = 0.0