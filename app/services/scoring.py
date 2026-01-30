"""Risk score and level computation; personalized tips from weakest tactics."""
from app.schemas.stats import TacticBreakdownSchema, TipSchema, AchievementSchema

# Risk score: start 50; wrong +10; correct -5; clamp 0..100
INITIAL_RISK_SCORE = 50
DELTA_WRONG = 10
DELTA_CORRECT = -5
MIN_SCORE = 0
MAX_SCORE = 100

LEVEL_BANDS = [
    (0, 20, "Security Ninja"),
    (21, 40, "Aware User"),
    (41, 60, "Rookie"),
    (61, 80, "At Risk"),
    (81, 100, "High Risk"),
]

# Russian display labels for levels (internal level key -> RU)
LEVEL_DISPLAY_RU = {
    "Security Ninja": "Мастер безопасности",
    "Aware User": "Осторожный пользователь",
    "Rookie": "Новичок",
    "At Risk": "В зоне риска",
    "High Risk": "Высокий риск",
}

# Russian display for tactics (internal tactic key -> RU)
TACTIC_DISPLAY_RU = {
    "Urgency": "Срочность",
    "Authority": "Авторитет",
    "Scarcity": "Дефицит",
    "Reciprocity": "Взаимность",
    "Fear": "Страх",
}

# Tips per tactic (Russian); internal tactic key
TACTIC_TIPS = {
    "Urgency": "Насторожитесь, если требуют срочных действий. Настоящие сервисы редко давят по времени.",
    "Authority": "Проверяйте личность тех, кто представляется IT, HR или руководством. Перезванивайте по известному номеру, не по ссылке.",
    "Scarcity": "«Осталось 5 мест» и ограниченные предложения — частый приём. Не спешите, проверьте информацию.",
    "Reciprocity": "Небольшая услуга создаёт ощущение долга. Вы не обязаны никому отдавать данные из-за этого.",
    "Fear": "Сообщения о блокировке или угрозах часто поддельные. Заходите через официальное приложение или сайт, не по ссылке из письма.",
}


def compute_level(risk_score: int) -> str:
    """Return level label from risk score (0-100)."""
    for low, high, label in LEVEL_BANDS:
        if low <= risk_score <= high:
            return label
    return "Rookie"  # fallback


def get_level_display_ru(risk_score: int) -> str:
    """Return Russian level label for display."""
    level = compute_level(risk_score)
    return LEVEL_DISPLAY_RU.get(level, level)


def get_tactic_display_ru(tactic: str) -> str:
    """Return Russian tactic label for display."""
    return TACTIC_DISPLAY_RU.get(tactic, tactic)


def apply_score_delta(current: int, delta: int) -> int:
    """Apply delta and clamp to 0..100."""
    return max(MIN_SCORE, min(MAX_SCORE, current + delta))


def get_tips_for_weak_tactics(breakdown: list[TacticBreakdownSchema], max_tips: int = 3) -> list[TipSchema]:
    """Return up to max_tips tips for tactics with highest mistake counts."""
    sorted_tactics = sorted(breakdown, key=lambda x: x.mistake_count, reverse=True)
    tips = []
    seen = set()
    for t in sorted_tactics:
        if t.mistake_count <= 0:
            continue
        if t.tactic in seen:
            continue
        seen.add(t.tactic)
        tip_text = TACTIC_TIPS.get(t.tactic)
        if tip_text:
            tips.append(TipSchema(tactic=t.tactic, tip=tip_text))
        if len(tips) >= max_tips:
            break
    for tactic, tip_text in TACTIC_TIPS.items():
        if len(tips) >= max_tips:
            break
        if tactic not in seen:
            tips.append(TipSchema(tactic=tactic, tip=tip_text))
            seen.add(tactic)
    return tips[:max_tips]


# Achievements: id -> (name_ru, condition description for reference)
ACHIEVEMENTS = [
    ("no_click_hero", "Без клика", "3 безопасных решения подряд"),
    ("phishing_detector", "Детектор фишинга", "5 безопасных решений всего"),
    ("calm_under_pressure", "Спокойствие под давлением", "2 безопасных в сценариях «Срочность»"),
]


def _max_consecutive_safe(attempts: list) -> int:
    """Compute max consecutive safe decisions from ordered attempts."""
    max_streak = 0
    current = 0
    for a in attempts:
        if getattr(a, "is_safe", None):
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def _urgency_safe_count(attempts: list) -> int:
    """Count safe decisions in Urgency scenarios."""
    return sum(1 for a in attempts if getattr(a, "tactic", None) == "Urgency" and getattr(a, "is_safe", False))


def compute_achievements(progress, attempts: list) -> list[AchievementSchema]:
    """Compute which achievements are unlocked from progress and attempts (ordered by id)."""
    max_streak = _max_consecutive_safe(attempts)
    urgency_safe = _urgency_safe_count(attempts)
    result = []
    result.append(AchievementSchema(
        id="no_click_hero",
        name_ru="Без клика",
        unlocked=max_streak >= 3,
    ))
    result.append(AchievementSchema(
        id="phishing_detector",
        name_ru="Детектор фишинга",
        unlocked=progress.correct_count >= 5,
    ))
    result.append(AchievementSchema(
        id="calm_under_pressure",
        name_ru="Спокойствие под давлением",
        unlocked=urgency_safe >= 2,
    ))
    return result
