"""Entry point for infodisplay."""

import logging
import sys

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


def run_render_test():
    """Render mock departures to test_output.png."""
    from infodisplay.renderer import run_render_test as _run_render_test

    output_path = _run_render_test()
    print(f"Rendered test output to: {output_path}")


def run_search(config):
    """Search for stations by name."""
    from infodisplay.api import BVGClient

    client = BVGClient(config)
    results = client.search_stations(config.search)
    if not results:
        print("No stations found.")
        return
    for i, loc in enumerate(results, 1):
        name = loc.get("name", "Unknown")
        loc_id = loc.get("id", "?")
        print(f"  {i}. {name}  [ID: {loc_id}]")


def run_app(config):
    """Run the full Pygame display application."""
    from infodisplay.app import InfoDisplayApp

    app = InfoDisplayApp(config)
    app.run()


def main():
    config = load_config()

    # Set up logging
    level = logging.DEBUG if config.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        if config.fetch_test:
            run_fetch_test(config)
        elif config.render_test:
            run_render_test()
        elif config.search:
            run_search(config)
        else:
            run_app(config)
    except KeyboardInterrupt:
        print("\nShutting down.")
        sys.exit(0)
    except Exception as e:
        logging.getLogger(__name__).error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
