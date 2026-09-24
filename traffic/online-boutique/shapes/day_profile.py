from locust import LoadTestShape

# Simulated daily traffic profile, replayed over a configurable cycle duration.
# Control points define (minute-of-day, user-count) pairs interpolated linearly.
#
# Default profile:
#   00h → night trough    (10 users)
#   06h → night trough    (10 users)
#   10h → morning peak    (80 users)
#   12h → lunch dip       (50 users)
#   14h → afternoon rise  (70 users)
#   19h → evening peak    (200 users)
#   22h → wind-down       (40 users)
#   24h → night trough    (10 users)

SPAWN_RATE = 5  # users/second for transitions

# Control points: (minute_of_day, user_count)
CONTROL_POINTS = [
    (0 * 60, 10),   # 00h - night trough
    (6 * 60, 10),   # 06h - night trough
    (10 * 60, 80),  # 10h - morning peak
    (12 * 60, 50),  # 12h - lunch dip
    (14 * 60, 70),  # 14h - afternoon rise
    (19 * 60, 200), # 19h - evening peak
    (22 * 60, 40),  # 22h - wind-down
    (24 * 60, 10),  # 24h - night trough
]


def _interpolate(points, t):
    """Linear interpolation between control points."""
    for i in range(len(points) - 1):
        t0, u0 = points[i]
        t1, u1 = points[i + 1]
        if t0 <= t <= t1:
            ratio = (t - t0) / (t1 - t0)
            return int(u0 + ratio * (u1 - u0))
    return points[-1][1]


class DayProfile(LoadTestShape):
    """
    Simulates a typical day in a continuous loop.
    The cycle duration is configurable via --duration-minutes (default: 1440 = real 24h).
    Reduce to accelerate, e.g. --duration-minutes 60 simulates a full day in 1 hour.
    """

    def tick(self):
        duration = self.runner.environment.parsed_options.duration_minutes
        total_seconds = duration * 60
        progress = (self.get_run_time() % total_seconds) / total_seconds
        simulated_minutes = progress * 24 * 60
        return (_interpolate(CONTROL_POINTS, simulated_minutes), SPAWN_RATE)
