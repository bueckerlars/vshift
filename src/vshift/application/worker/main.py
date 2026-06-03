from vshift.application.worker.application_context import WorkerApplicationContext


def main() -> None:
    """
    Main function for the application.
    """
    context = WorkerApplicationContext()
    context._log_settings()


if __name__ == "__main__":
    main()
