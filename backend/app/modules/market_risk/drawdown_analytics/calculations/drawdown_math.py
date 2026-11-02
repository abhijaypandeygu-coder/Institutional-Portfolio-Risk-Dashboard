"""
Module M07.04: Drawdown Analytics Mathematical Formulas.
Implements:
1. Running High-Water Mark (HWM_t = max(V_0, ..., V_t)).
2. Signed percentage drawdown: D_t = (V_t / HWM_t) - 1.
3. Positive drawdown magnitude: DD_t = 1 - (V_t / HWM_t) (expressed as positive %).
4. Absolute drawdown amount: DD_t^{Amount} = HWM_t - V_t.
5. Maximum Drawdown (MDD) identification with deterministic tie-breaking.
6. Linear-pass Drawdown Episode detection (peak, trough, recovery, ongoing right-censoring).
7. Recovery and underwater duration calculations.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownEpisodeStatus,
    HighWaterMarkPolicy,
)

PRECISION_FOUR = Decimal("0.0001")
PRECISION_SIX = Decimal("0.000001")
PRECISION_EIGHT = Decimal("0.00000001")


def calculate_drawdown_series(
    observations: List[Tuple[datetime, Decimal]],
    high_water_mark_policy: HighWaterMarkPolicy = HighWaterMarkPolicy.FULL_HISTORY_HIGH_WATER_MARK,
    recovery_tolerance: Decimal = Decimal("0.00000001"),
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Single linear pass O(n) computing:
    1. Running time-series points: (timestamp, value, HWM, HWM_timestamp, signed_dd, dd_pct, dd_amount, episode_id)
    2. Discrete Drawdown Episodes: (episode_id, peak_val, peak_ts, trough_val, trough_ts, recovery_val, recovery_ts,
       drawdown_pct, signed_dd, dd_amount, peak_to_trough_days, trough_to_recovery_days, underwater_days, status)
    3. Maximum Drawdown Record.
    """
    if not observations:
        return [], [], None

    # Sort observations chronologically
    sorted_obs = sorted(observations, key=lambda x: x[0])
    n = len(sorted_obs)

    series_points: List[Dict[str, Any]] = []
    episodes: List[Dict[str, Any]] = []

    # Running state
    running_hwm = sorted_obs[0][1]
    running_hwm_ts = sorted_obs[0][0]

    current_episode: Optional[Dict[str, Any]] = None
    episode_seq = 1

    max_dd_val = Decimal("0.0")
    max_dd_record: Optional[Dict[str, Any]] = None

    for idx, (obs_ts, val) in enumerate(sorted_obs):
        # Update running peak
        if val > running_hwm:
            # We reached a new high-water mark
            if current_episode is not None:
                # Prior episode is now recovered
                current_episode["recovery_value"] = val
                current_episode["recovery_timestamp"] = obs_ts
                current_episode["episode_status"] = DrawdownEpisodeStatus.RECOVERED

                # Durations
                p_ts = current_episode["peak_timestamp"]
                t_ts = current_episode["trough_timestamp"]
                current_episode["trough_to_recovery_days"] = max(0, (obs_ts - t_ts).days)
                current_episode["underwater_duration_days"] = max(0, (obs_ts - p_ts).days)
                episodes.append(current_episode)
                current_episode = None

            running_hwm = val
            running_hwm_ts = obs_ts
            signed_dd = Decimal("0.0")
            dd_pct = Decimal("0.0")
            dd_amount = Decimal("0.0")
            ep_id = None
            ep_status = None
        else:
            # Below or equal to running high-water mark
            # D_t = (V_t / HWM_t) - 1
            signed_dd = ((val / running_hwm) - Decimal("1.0")).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
            dd_pct = (-signed_dd * Decimal("100.0")).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP)
            dd_amount = (running_hwm - val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if dd_amount > recovery_tolerance:
                # Active drawdown
                if current_episode is None:
                    # Start new episode from the running high-water mark
                    current_episode = {
                        "episode_id": f"EP_{episode_seq:04d}",
                        "peak_value": running_hwm,
                        "peak_timestamp": running_hwm_ts,
                        "trough_value": val,
                        "trough_timestamp": obs_ts,
                        "recovery_value": None,
                        "recovery_timestamp": None,
                        "drawdown_percentage": dd_pct,
                        "signed_drawdown": signed_dd,
                        "absolute_drawdown_amount": dd_amount,
                        "peak_to_trough_days": max(0, (obs_ts - running_hwm_ts).days),
                        "trough_to_recovery_days": None,
                        "underwater_duration_days": max(0, (obs_ts - running_hwm_ts).days),
                        "trading_sessions_count": 1,
                        "observation_count": 1,
                        "episode_status": DrawdownEpisodeStatus.ONGOING,
                        "as_of_timestamp": obs_ts,
                    }
                    episode_seq += 1
                else:
                    # Update active episode
                    current_episode["observation_count"] += 1
                    current_episode["as_of_timestamp"] = obs_ts
                    current_episode["underwater_duration_days"] = max(
                        0, (obs_ts - current_episode["peak_timestamp"]).days
                    )

                    # Check for deeper trough
                    if val < current_episode["trough_value"]:
                        current_episode["trough_value"] = val
                        current_episode["trough_timestamp"] = obs_ts
                        current_episode["drawdown_percentage"] = dd_pct
                        current_episode["signed_drawdown"] = signed_dd
                        current_episode["absolute_drawdown_amount"] = dd_amount
                        current_episode["peak_to_trough_days"] = max(
                            0, (obs_ts - current_episode["peak_timestamp"]).days
                        )

                ep_id = current_episode["episode_id"]
                ep_status = current_episode["episode_status"].value
            else:
                # Equal to peak within tolerance
                if current_episode is not None:
                    current_episode["recovery_value"] = val
                    current_episode["recovery_timestamp"] = obs_ts
                    current_episode["episode_status"] = DrawdownEpisodeStatus.RECOVERED
                    p_ts = current_episode["peak_timestamp"]
                    t_ts = current_episode["trough_timestamp"]
                    current_episode["trough_to_recovery_days"] = max(0, (obs_ts - t_ts).days)
                    current_episode["underwater_duration_days"] = max(0, (obs_ts - p_ts).days)
                    episodes.append(current_episode)
                    current_episode = None

                signed_dd = Decimal("0.0")
                dd_pct = Decimal("0.0")
                dd_amount = Decimal("0.0")
                ep_id = None
                ep_status = None

        # Track global maximum drawdown
        if dd_pct > max_dd_val:
            max_dd_val = dd_pct
            max_dd_record = {
                "maximum_drawdown_percentage": dd_pct,
                "signed_maximum_drawdown": signed_dd,
                "maximum_drawdown_amount": dd_amount,
                "peak_episode_id": ep_id,
                "peak_value": running_hwm,
                "peak_timestamp": running_hwm_ts,
                "trough_value": val,
                "trough_timestamp": obs_ts,
                "recovery_timestamp": None,
                "peak_to_trough_days": max(0, (obs_ts - running_hwm_ts).days),
                "trough_to_recovery_days": None,
                "underwater_duration_days": max(0, (obs_ts - running_hwm_ts).days),
                "recovery_status": DrawdownEpisodeStatus.ONGOING,
            }

        series_points.append({
            "observation_timestamp": obs_ts,
            "observation_date": obs_ts.date(),
            "selected_value": val,
            "running_high_water_mark": running_hwm,
            "high_water_mark_timestamp": running_hwm_ts,
            "signed_drawdown": signed_dd,
            "drawdown_percentage": dd_pct,
            "absolute_drawdown_amount": dd_amount,
            "episode_id": ep_id,
            "episode_status": ep_status,
        })

    # Close any ongoing episode at the end of the window as right-censored
    if current_episode is not None:
        episodes.append(current_episode)

    # If max_dd_record belongs to an episode that subsequently recovered, update recovery info
    if max_dd_record and max_dd_record["peak_episode_id"]:
        for ep in episodes:
            if ep["episode_id"] == max_dd_record["peak_episode_id"]:
                max_dd_record["recovery_timestamp"] = ep["recovery_timestamp"]
                max_dd_record["recovery_status"] = ep["episode_status"]
                max_dd_record["trough_to_recovery_days"] = ep["trough_to_recovery_days"]
                max_dd_record["underwater_duration_days"] = ep["underwater_duration_days"]
                break

    # If no drawdown occurred throughout history (strictly monotonically increasing)
    if max_dd_record is None:
        last_obs = sorted_obs[-1]
        max_dd_record = {
            "maximum_drawdown_percentage": Decimal("0.0"),
            "signed_maximum_drawdown": Decimal("0.0"),
            "maximum_drawdown_amount": Decimal("0.0"),
            "peak_episode_id": None,
            "peak_value": last_obs[1],
            "peak_timestamp": last_obs[0],
            "trough_value": last_obs[1],
            "trough_timestamp": last_obs[0],
            "recovery_timestamp": last_obs[0],
            "peak_to_trough_days": 0,
            "trough_to_recovery_days": 0,
            "underwater_duration_days": 0,
            "recovery_status": DrawdownEpisodeStatus.RECOVERED,
        }

    return series_points, episodes, max_dd_record


def calculate_recovery_summary_statistics(
    episodes: List[Dict[str, Any]], as_of_dt: date
) -> Dict[str, Any]:
    """
    Computes completed recovery and underwater statistics.
    Excludes right-censored ongoing episodes from completed recovery metrics.
    """
    total_count = len(episodes)
    completed_eps = [ep for ep in episodes if ep["episode_status"] == DrawdownEpisodeStatus.RECOVERED]
    ongoing_eps = [ep for ep in episodes if ep["episode_status"] != DrawdownEpisodeStatus.RECOVERED]

    completed_count = len(completed_eps)
    ongoing_count = len(ongoing_eps)

    if completed_count > 0:
        rec_durations = [ep["trough_to_recovery_days"] for ep in completed_eps if ep["trough_to_recovery_days"] is not None]
        avg_rec = (Decimal(str(np.mean(rec_durations)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        med_rec = (Decimal(str(np.median(rec_durations)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        longest_rec = max(rec_durations) if rec_durations else 0
        shortest_rec = min(rec_durations) if rec_durations else 0
    else:
        avg_rec = None
        med_rec = None
        longest_rec = None
        shortest_rec = None

    if total_count > 0:
        p2t_durations = [ep["peak_to_trough_days"] for ep in episodes]
        underwater_durations = [ep["underwater_duration_days"] for ep in episodes]
        avg_p2t = (Decimal(str(np.mean(p2t_durations)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        avg_underwater = (Decimal(str(np.mean(underwater_durations)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        longest_underwater = max(underwater_durations)
    else:
        avg_p2t = Decimal("0.0")
        avg_underwater = Decimal("0.0")
        longest_underwater = 0

    return {
        "total_episodes_count": total_count,
        "completed_episodes_count": completed_count,
        "ongoing_episodes_count": ongoing_count,
        "average_recovery_days": avg_rec,
        "median_recovery_days": med_rec,
        "longest_recovery_days": longest_rec,
        "shortest_recovery_days": shortest_rec,
        "average_peak_to_trough_days": avg_p2t,
        "average_underwater_days": avg_underwater,
        "longest_underwater_days": longest_underwater,
        "as_of_date": as_of_dt,
    }
