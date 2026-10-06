from resources.lib.modules.globals import g

# from resources.lib.common import maintenance


def do_version_change():
    if g.get_setting("prism.version") == g.CLEAN_VERSION:
        return

    g.log("Clearing cache on Prism version change", "info")
    g.clear_cache(silent=True)
    _clear_uncached_debrid_hashes()

    g.set_setting("prism.version", g.CLEAN_VERSION)

    # Reuselanguageinvoker update.  This should be last to execute as it can do a profile reload.

    # Disable the restoration of reuselanguageinvoker addon.xml based on settings value on upgrade.
    # It can still be toggled in settings, although initially it will be the release default value.
    # This is due to the fact that we still don't recommend having this enabled due to Kodi hard crashes.
    # maintenance.toggle_reuselanguageinvoker(
    #     True if g.get_setting("reuselanguageinvoker") == "Enabled" else False)
    g.set_setting(
        "reuselanguageinvoker.status", "Disabled"
    )  # This ensures setting is reflected as disabled on version change


def _clear_uncached_debrid_hashes():
    """
    Hashes stored as uncached are not rechecked for 4 h. A release may fix a cache check that
    wrote wrong negatives (5.0.57: broken DMM check), so drop them on every version change.
    """
    try:
        g.log("Clearing uncached debrid hashes on Prism version change", "info")
        from resources.lib.database.debridCache import DebridCache

        DebridCache().clear_uncached_entries()
    except Exception:
        g.log_stacktrace()
