"""Read both current and legacy CRM SPOC assignments."""


def spoc_ids(profile):
    profile = profile or {}
    if "spoc_ids" in profile:
        return profile["spoc_ids"]
    identifier = profile.get("spoc_id")
    return [identifier] if identifier is not None else []


def has_spoc_assignment(profile):
    return "spoc_ids" in profile or "spoc_id" in profile
