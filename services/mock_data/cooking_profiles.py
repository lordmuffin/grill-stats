#!/usr/bin/env python3
"""
Cooking Profiles for Mock Data Service

This module provides realistic cooking profiles for different meat types and cooking methods.
Each profile defines temperature progression patterns, cooking times, and recommended temperatures.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class CookingMethod(Enum):
    """Cooking methods that affect temperature patterns"""

    SMOKING = "smoking"  # Low and slow
    GRILLING = "grilling"  # High and fast
    ROASTING = "roasting"  # Medium heat, consistent
    SOUS_VIDE = "sous_vide"  # Precision low temp
    BRAISING = "braising"  # Low heat with moisture


class MeatType(Enum):
    """Types of meat with different cooking characteristics"""

    BEEF_BRISKET = "beef_brisket"
    BEEF_STEAK = "beef_steak"
    BEEF_ROAST = "beef_roast"
    PORK_SHOULDER = "pork_shoulder"
    PORK_RIBS = "pork_ribs"
    PORK_LOIN = "pork_loin"
    CHICKEN_WHOLE = "chicken_whole"
    CHICKEN_BREAST = "chicken_breast"
    CHICKEN_THIGH = "chicken_thigh"
    TURKEY_WHOLE = "turkey_whole"
    FISH = "fish"
    LAMB = "lamb"


@dataclass
class TemperaturePhase:
    """Represents a phase in the cooking process with specific temperature behavior"""

    name: str  # Phase name (e.g., "initial rise", "stall", "final rise")
    duration_range: Tuple[float, float]  # Min/max duration in minutes
    rate_range: Tuple[float, float]  # Min/max temperature change rate (degrees per minute)
    target_temp_range: Optional[Tuple[float, float]] = None  # Target temperature range for this phase
    volatility: float = 0.5  # How much random variation to apply
    target_based: bool = False  # Whether rate is replaced by approach to target


@dataclass
class CookingProfile:
    """Complete cooking profile for a specific meat and cooking method"""

    meat_type: MeatType
    cooking_method: CookingMethod
    phases: List[TemperaturePhase]
    starting_temp_range: Tuple[float, float]  # Starting internal temperature range
    final_temp_range: Tuple[float, float]  # Final/done temperature range
    description: str = ""  # Human-readable description


# =============================================================================
# Cooking Profiles - Based on typical time/temp progressions
# =============================================================================

# Beef Brisket - Smoking
BRISKET_SMOKING = CookingProfile(
    meat_type=MeatType.BEEF_BRISKET,
    cooking_method=CookingMethod.SMOKING,
    description="Low and slow smoked brisket with stall phase",
    starting_temp_range=(35.0, 45.0),  # Starting from refrigerator temp
    final_temp_range=(195.0, 205.0),  # Final done temp
    phases=[
        # Initial rise - faster warming as meat takes on heat
        TemperaturePhase(
            name="initial_rise",
            duration_range=(60.0, 120.0),  # 1-2 hours
            rate_range=(1.0, 1.5),  # 1-1.5°F per minute
            volatility=0.3,
        ),
        # Stall phase - moisture evaporation keeps temp steady
        TemperaturePhase(
            name="stall",
            duration_range=(120.0, 240.0),  # 2-4 hours
            rate_range=(0.05, 0.15),  # Very slow rise during stall
            target_temp_range=(150.0, 170.0),  # Stall usually happens around 150-170°F
            volatility=0.2,
            target_based=True,
        ),
        # Final rise - after stall, temp rises again
        TemperaturePhase(
            name="final_rise",
            duration_range=(60.0, 180.0),  # 1-3 hours
            rate_range=(0.2, 0.4),  # 0.2-0.4°F per minute
            volatility=0.4,
        ),
    ],
)

# Beef Steak - Grilling
STEAK_GRILLING = CookingProfile(
    meat_type=MeatType.BEEF_STEAK,
    cooking_method=CookingMethod.GRILLING,
    description="High heat grilled steak",
    starting_temp_range=(35.0, 65.0),  # Starting from refrigerator or room temp
    final_temp_range=(125.0, 155.0),  # Rare to well done
    phases=[
        # Quick temperature rise
        TemperaturePhase(
            name="rapid_rise",
            duration_range=(3.0, 15.0),  # 3-15 minutes depending on thickness and doneness
            rate_range=(3.0, 10.0),  # Very fast temp increase
            volatility=1.0,
        ),
        # Resting phase (if monitored during rest)
        TemperaturePhase(
            name="resting",
            duration_range=(3.0, 10.0),  # 3-10 minutes rest
            rate_range=(-0.3, 0.1),  # Slight decrease or plateau during rest
            volatility=0.2,
        ),
    ],
)

# Pork Shoulder - Smoking
PORK_SHOULDER_SMOKING = CookingProfile(
    meat_type=MeatType.PORK_SHOULDER,
    cooking_method=CookingMethod.SMOKING,
    description="Low and slow smoked pork shoulder (pulled pork)",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(195.0, 205.0),
    phases=[
        # Initial rise
        TemperaturePhase(
            name="initial_rise",
            duration_range=(90.0, 180.0),  # 1.5-3 hours
            rate_range=(0.8, 1.2),  # 0.8-1.2°F per minute
            volatility=0.4,
        ),
        # Stall phase
        TemperaturePhase(
            name="stall",
            duration_range=(120.0, 300.0),  # 2-5 hours
            rate_range=(0.05, 0.2),  # Very slow rise during stall
            target_temp_range=(150.0, 170.0),
            volatility=0.3,
            target_based=True,
        ),
        # Final rise
        TemperaturePhase(
            name="final_rise",
            duration_range=(60.0, 180.0),  # 1-3 hours
            rate_range=(0.2, 0.5),  # 0.2-0.5°F per minute
            volatility=0.4,
        ),
    ],
)

# Pork Ribs - Smoking
PORK_RIBS_SMOKING = CookingProfile(
    meat_type=MeatType.PORK_RIBS,
    cooking_method=CookingMethod.SMOKING,
    description="Smoked pork ribs",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(190.0, 203.0),
    phases=[
        # Initial rise
        TemperaturePhase(
            name="initial_rise",
            duration_range=(45.0, 90.0),  # 45-90 minutes
            rate_range=(1.0, 1.8),  # 1.0-1.8°F per minute
            volatility=0.5,
        ),
        # Middle phase
        TemperaturePhase(
            name="middle_phase",
            duration_range=(60.0, 120.0),  # 1-2 hours
            rate_range=(0.3, 0.7),  # 0.3-0.7°F per minute
            volatility=0.4,
        ),
        # Final rise
        TemperaturePhase(
            name="final_rise",
            duration_range=(30.0, 90.0),  # 30-90 minutes
            rate_range=(0.2, 0.5),  # 0.2-0.5°F per minute
            volatility=0.3,
        ),
    ],
)

# Chicken Whole - Roasting
CHICKEN_WHOLE_ROASTING = CookingProfile(
    meat_type=MeatType.CHICKEN_WHOLE,
    cooking_method=CookingMethod.ROASTING,
    description="Whole roasted chicken",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(165.0, 175.0),
    phases=[
        # Initial rise
        TemperaturePhase(
            name="initial_rise",
            duration_range=(15.0, 30.0),  # 15-30 minutes
            rate_range=(2.0, 3.0),  # 2.0-3.0°F per minute
            volatility=0.6,
        ),
        # Middle phase
        TemperaturePhase(
            name="middle_phase",
            duration_range=(30.0, 60.0),  # 30-60 minutes
            rate_range=(1.0, 1.5),  # 1.0-1.5°F per minute
            volatility=0.4,
        ),
        # Final approach
        TemperaturePhase(
            name="final_approach",
            duration_range=(15.0, 30.0),  # 15-30 minutes
            rate_range=(0.5, 1.0),  # 0.5-1.0°F per minute
            target_temp_range=(165.0, 175.0),
            volatility=0.3,
            target_based=True,
        ),
    ],
)

# Chicken Breast - Grilling
CHICKEN_BREAST_GRILLING = CookingProfile(
    meat_type=MeatType.CHICKEN_BREAST,
    cooking_method=CookingMethod.GRILLING,
    description="Grilled chicken breast",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(160.0, 165.0),
    phases=[
        # Rapid rise
        TemperaturePhase(
            name="rapid_rise",
            duration_range=(5.0, 15.0),  # 5-15 minutes
            rate_range=(3.0, 5.0),  # 3.0-5.0°F per minute
            volatility=0.7,
        ),
        # Final approach
        TemperaturePhase(
            name="final_approach",
            duration_range=(3.0, 10.0),  # 3-10 minutes
            rate_range=(1.0, 2.0),  # 1.0-2.0°F per minute
            target_temp_range=(160.0, 165.0),
            volatility=0.5,
            target_based=True,
        ),
    ],
)

# Fish - Grilling
FISH_GRILLING = CookingProfile(
    meat_type=MeatType.FISH,
    cooking_method=CookingMethod.GRILLING,
    description="Grilled fish fillet",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(135.0, 145.0),
    phases=[
        # Very quick temperature rise
        TemperaturePhase(
            name="rapid_rise",
            duration_range=(2.0, 8.0),  # 2-8 minutes
            rate_range=(6.0, 12.0),  # Very fast temp increase
            volatility=1.2,
        ),
        # Final approach
        TemperaturePhase(
            name="final_approach",
            duration_range=(1.0, 3.0),  # 1-3 minutes
            rate_range=(2.0, 4.0),  # 2.0-4.0°F per minute
            target_temp_range=(135.0, 145.0),
            volatility=0.5,
            target_based=True,
        ),
    ],
)

# Turkey Whole - Roasting
TURKEY_WHOLE_ROASTING = CookingProfile(
    meat_type=MeatType.TURKEY_WHOLE,
    cooking_method=CookingMethod.ROASTING,
    description="Whole roasted turkey",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(165.0, 175.0),
    phases=[
        # Initial rise
        TemperaturePhase(
            name="initial_rise",
            duration_range=(45.0, 90.0),  # 45-90 minutes
            rate_range=(1.0, 2.0),  # 1.0-2.0°F per minute
            volatility=0.5,
        ),
        # Middle phase
        TemperaturePhase(
            name="middle_phase",
            duration_range=(90.0, 180.0),  # 1.5-3 hours
            rate_range=(0.5, 1.0),  # 0.5-1.0°F per minute
            volatility=0.4,
        ),
        # Final approach
        TemperaturePhase(
            name="final_approach",
            duration_range=(30.0, 60.0),  # 30-60 minutes
            rate_range=(0.3, 0.6),  # 0.3-0.6°F per minute
            target_temp_range=(165.0, 175.0),
            volatility=0.3,
            target_based=True,
        ),
    ],
)

# Dictionary of all profiles
COOKING_PROFILES: Dict[str, CookingProfile] = {
    f"{profile.meat_type.value}_{profile.cooking_method.value}": profile
    for profile in [
        BRISKET_SMOKING,
        STEAK_GRILLING,
        PORK_SHOULDER_SMOKING,
        PORK_RIBS_SMOKING,
        CHICKEN_WHOLE_ROASTING,
        CHICKEN_BREAST_GRILLING,
        FISH_GRILLING,
        TURKEY_WHOLE_ROASTING,
    ]
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_profile_by_name(meat_name: str) -> Optional[CookingProfile]:
    """
    Get the most appropriate cooking profile based on a probe name.

    Args:
        meat_name: The name of the probe/meat (e.g., "Brisket Internal")

    Returns:
        The matching cooking profile or None if no match found
    """
    meat_name = meat_name.lower()

    # Direct mapping of keywords to profiles
    keyword_map = {
        "brisket": "beef_brisket_smoking",
        "steak": "beef_steak_grilling",
        "pork shoulder": "pork_shoulder_smoking",
        "pulled pork": "pork_shoulder_smoking",
        "ribs": "pork_ribs_smoking",
        "pork ribs": "pork_ribs_smoking",
        "chicken breast": "chicken_breast_grilling",
        "chicken whole": "chicken_whole_roasting",
        "whole chicken": "chicken_whole_roasting",
        "fish": "fish_grilling",
        "turkey": "turkey_whole_roasting",
    }

    # Try direct mapping first
    for keyword, profile_name in keyword_map.items():
        if keyword in meat_name:
            return COOKING_PROFILES.get(profile_name)

    # Fallback to more generic matching
    if "beef" in meat_name:
        if "roast" in meat_name:
            return COOKING_PROFILES.get("beef_roast_roasting", COOKING_PROFILES.get("beef_brisket_smoking"))
        return COOKING_PROFILES.get("beef_steak_grilling")

    if "pork" in meat_name:
        return COOKING_PROFILES.get("pork_loin_roasting", COOKING_PROFILES.get("pork_shoulder_smoking"))

    if "chicken" in meat_name:
        return COOKING_PROFILES.get("chicken_breast_grilling")

    # Default to steak for unrecognized food items
    if "food" in meat_name:
        return COOKING_PROFILES.get("beef_steak_grilling")

    return None


def get_ambient_profile_for_cooking_method(cooking_method: CookingMethod) -> Dict[str, float]:
    """
    Get ambient temperature profile (for smoker/grill) based on cooking method.

    Args:
        cooking_method: The cooking method being used

    Returns:
        Dictionary with ambient temperature parameters
    """
    if cooking_method == CookingMethod.SMOKING:
        return {
            "target_temp": random.uniform(225.0, 275.0),
            "volatility": random.uniform(5.0, 15.0),
            "recovery_rate": random.uniform(1.0, 3.0),  # °F per minute recovery after opening
        }

    elif cooking_method == CookingMethod.GRILLING:
        return {
            "target_temp": random.uniform(350.0, 450.0),
            "volatility": random.uniform(15.0, 30.0),
            "recovery_rate": random.uniform(5.0, 10.0),
        }

    elif cooking_method == CookingMethod.ROASTING:
        return {
            "target_temp": random.uniform(325.0, 375.0),
            "volatility": random.uniform(3.0, 8.0),
            "recovery_rate": random.uniform(2.0, 5.0),
        }

    # Default/fallback
    return {
        "target_temp": random.uniform(250.0, 350.0),
        "volatility": random.uniform(5.0, 20.0),
        "recovery_rate": random.uniform(2.0, 5.0),
    }


def generate_cooking_event(
    elapsed_minutes: float, cooking_duration: float, cooking_method: CookingMethod
) -> Optional[Dict[str, Any]]:
    """
    Generate random cooking events based on elapsed time and cooking method.

    Args:
        elapsed_minutes: Minutes elapsed since cooking started
        cooking_duration: Expected total cooking duration in minutes
        cooking_method: The cooking method being used

    Returns:
        Event dictionary or None if no event occurred
    """
    # Early return most of the time (no event)
    if random.random() < 0.95:  # Only 5% chance of an event per check
        return None

    # Calculate progress through the cook (0-1)
    progress = min(1.0, elapsed_minutes / cooking_duration)

    # Possible events
    events = []

    # Lid opening events - more likely for grilling, less for sous vide
    if cooking_method in [CookingMethod.GRILLING, CookingMethod.SMOKING, CookingMethod.ROASTING]:
        lid_open_likelihood = {
            CookingMethod.GRILLING: 0.6,
            CookingMethod.SMOKING: 0.3,
            CookingMethod.ROASTING: 0.2,
        }.get(cooking_method, 0.2)

        # Modified by progress - more likely in middle of cook
        if 0.2 < progress < 0.8:
            lid_open_likelihood *= 1.5

        if random.random() < lid_open_likelihood:
            events.append(
                {
                    "type": "lid_open",
                    "duration": random.uniform(0.5, 3.0),  # Minutes
                    "temp_drop": random.uniform(5.0, 25.0)
                    * {
                        CookingMethod.GRILLING: 1.5,
                        CookingMethod.SMOKING: 1.0,
                        CookingMethod.ROASTING: 0.8,
                    }.get(cooking_method, 1.0),
                }
            )

    # Temperature adjustment events - more likely for smoking, early in cook
    if cooking_method in [CookingMethod.SMOKING, CookingMethod.ROASTING]:
        temp_adjust_likelihood = {
            CookingMethod.SMOKING: 0.4,
            CookingMethod.ROASTING: 0.2,
        }.get(cooking_method, 0.1)

        # More likely early in cook
        if progress < 0.3:
            temp_adjust_likelihood *= 2.0

        if random.random() < temp_adjust_likelihood:
            events.append(
                {
                    "type": "temp_adjustment",
                    "direction": random.choice(["up", "down"]),
                    "amount": random.uniform(10.0, 30.0),
                }
            )

    # Fuel/wood added - specific to smoking
    if cooking_method == CookingMethod.SMOKING:
        if random.random() < 0.3 and progress > 0.4:  # More likely later in cook
            events.append(
                {
                    "type": "fuel_added",
                    "temp_spike": random.uniform(5.0, 15.0),
                    "recovery_time": random.uniform(5.0, 15.0),  # Minutes
                }
            )

    # Basting/spraying - for longer cooks
    if cooking_method in [CookingMethod.SMOKING, CookingMethod.ROASTING]:
        if random.random() < 0.2 and progress > 0.3:
            events.append(
                {
                    "type": "basting",
                    "temp_drop": random.uniform(2.0, 5.0),
                    "recovery_time": random.uniform(1.0, 3.0),  # Minutes
                }
            )

    # Flipping food - for grilling
    if cooking_method == CookingMethod.GRILLING:
        # More likely in first half of cook
        if random.random() < 0.4 and progress < 0.6:
            events.append(
                {
                    "type": "flip_food",
                    "temp_plateau": random.uniform(0.5, 2.0),  # Minutes of plateau
                }
            )

    # Return a random event if we have any
    if events:
        return random.choice(events)

    return None
