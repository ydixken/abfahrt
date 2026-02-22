"""Entry point for infodisplay."""

from infodisplay.config import load_config


def run_fetch_test(config):
    """Fetch and print live departures for all configured stations."""
    from infodisplay.api import BVGClient

    client = BVGClient(config)
    for station_cfg in config.stations:
        station_name = station_cfg.name or client.get_station_name(station_cfg.id)
        print(f"\n=== {station_name} ({station_cfg.id}) ===\n")

        departures = client.fetch_parsed_departures(station_cfg.id)
        if not departures:
            print("  Keine Abfahrten")
            continue

        for dep in departures:
            remarks_str = ", ".join(dep.remarks) if dep.remarks else ""
            minutes = dep.minutes_until
            min_str = f"{minutes} min" if minutes is not None else "?"
            delay_str = f"+{dep.delay_minutes}" if dep.delay_seconds else "+0"
            print(
                f"  {dep.line_name:<5}| {dep.direction:<25}| "
                f"{remarks_str:<25}| {min_str:>6} | {delay_str}"
            )


def main():
    config = load_config()

    if config.fetch_test:
        run_fetch_test(config)
        return

    if config.search:
        from infodisplay.api import BVGClient

        client = BVGClient(config)
        results = client.search_stations(config.search)
        for i, loc in enumerate(results, 1):
            name = loc.get("name", "Unknown")
            loc_id = loc.get("id", "?")
            print(f"  {i}. {name}  [ID: {loc_id}]")
        return

    print("infodisplay - use --fetch-test, --render-test, or --search")


if __name__ == "__main__":
    main()
