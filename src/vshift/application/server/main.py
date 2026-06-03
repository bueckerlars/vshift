from vshift.application.server.application_context import ServerApplicationContext


def main() -> None:
    """
    Main function for the application.
    """
    context = ServerApplicationContext()
    context._log_settings()


if __name__ == "__main__":
    main()
