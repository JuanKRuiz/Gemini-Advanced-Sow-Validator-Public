#@title Colab Entry Point, Execute Process!
# This entry point is designed for a Colab environment.
# It expects the SoW URL to be passed as a command-line argument.
# Example from a notebook cell: !python main_execution.py "your_sow_url_here"

from application import Application


app = Application(environment='colab')
app.run(sow_url=SOW_URL) # pyright: ignore[reportUndefinedVariable]

