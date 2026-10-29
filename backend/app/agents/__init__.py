from .analytics import AnalyticsAgent
from .base import Agent
from .niche_analyst import NicheAnalyst
from .quality import QualityCompliance
from .reality_kitchen import RealityKitchenStories
from .retention import RetentionStrategist
from .scriptwriter import Scriptwriter
from .trend_hunter import TrendHunter
from .video_producer import VideoProducer
from .visual_hunter import VisualHunter

AGENTS: dict[str, Agent] = {
    a.name: a
    for a in (TrendHunter(), NicheAnalyst(), RetentionStrategist(), Scriptwriter(), VideoProducer(),
              QualityCompliance(), AnalyticsAgent(), RealityKitchenStories(), VisualHunter())
}
TASK_ROUTES: dict[str, str] = {t: a.name for a in AGENTS.values() for t in a.task_types}
