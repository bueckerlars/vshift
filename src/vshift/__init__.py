from importlib.metadata import metadata, version

__app_name__ = metadata("vshift")["Name"]
__version__ = version("vshift")
