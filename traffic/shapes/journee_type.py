from locust import LoadTestShape

# Profil journalier simulé sur une durée configurable.
# La courbe est définie par des points de contrôle (heure, users)
# interpolés linéairement.
#
# Profil par défaut :
#   00h → creux nuit    (10 users)
#   06h → creux nuit    (10 users)
#   10h → bosse matin   (80 users)
#   12h → creux midi    (50 users)
#   14h → reprise      (70 users)
#   19h → pic soir     (200 users)
#   22h → descente      (40 users)
#   24h → creux nuit    (10 users)

SPAWN_RATE = 5  # users/seconde pour les transitions

# Points de contrôle : (heure_en_minutes, users)
CONTROL_POINTS = [
    (0   * 60,  10),   # 00h - creux nuit
    (6   * 60,  10),   # 00h - creux nuit
    (10  * 60,  80),   # 07h - bosse matin
    (12  * 60,  50),   # 12h - creux midi
    (14  * 60,  70),   # 14h - reprise après-midi
    (19  * 60, 200),   # 19h - pic soir
    (22  * 60,  40),   # 22h - descente
    (24  * 60,  10),   # 24h - creux nuit
]


def _interpolate(points, t):
    """Interpolation linéaire entre les points de contrôle."""
    for i in range(len(points) - 1):
        t0, u0 = points[i]
        t1, u1 = points[i + 1]
        if t0 <= t <= t1:
            ratio = (t - t0) / (t1 - t0)
            return int(u0 + ratio * (u1 - u0))
    return points[-1][1]


class JourneeType(LoadTestShape):
    """
    Simulates a typical day in a continuous loop.
    The cycle duration is configurable via --duration-minutes (default: 1440 = real 24h).
    Reduce to accelerate, e.g. --duration-minutes 60 simulates a full day in 1 hour.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duration = self.runner.environment.parsed_options.duration_minutes

    def tick(self):
        total_seconds = self.duration * 60
        progress = (self.get_run_time() % total_seconds) / total_seconds
        simulated_minutes = progress * 24 * 60
        return (_interpolate(CONTROL_POINTS, simulated_minutes), SPAWN_RATE)
