from safe_intent_sdn import create_run_context, load_settings


def main() -> None:
    settings = load_settings()
    with create_run_context(settings, intent_id="manual") as run:
        run.log_event("application_ready", stage="startup")


if __name__ == "__main__":
    main()
