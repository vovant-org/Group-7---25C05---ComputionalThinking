"""Topic-aware Visual Engine for the ANIMATION format.

The generic cut-out animation (modules/video/animation.py) draws the SAME stick figure and the SAME six
props for every topic. This package makes the picture depend on WHAT the narration says:

  1. topic.py     analyse the topic     -> domain, audience, concepts, relations        (deterministic lexicon)
  2. kits.py      choose a visual kit   -> backdrop, actor, objects of the domain       (lookup tables)
  3. objects.py   motion by content     -> animals walk, plants grow, planets orbit, money circulates ...
  4. sync.py      voice-over sync       -> an object appears when the narrator MENTIONS it
  5. quality.py   quality checks        -> empty scenes, repeated visuals, subtitles, audio, duration
  engine.py ties them together: `analyse_topic` once per video, `compose_topic_scenes` for all scenes.

No AI model is used: the same input gives the same frames (report: Determinism). Every text/number on screen
still comes from claims; objects are drawn without text (nothing for an image model to misspell).
"""
from modules.visual_engine.engine import TopicScene, compose_topic_scenes  # noqa: E402,F401
from modules.visual_engine.topic import TopicProfile, analyse_topic  # noqa: E402,F401
