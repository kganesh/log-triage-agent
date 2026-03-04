"""A small LangChain agent that reads a log file and explains what went wrong.

The agent has four tools for navigating a log. It must report line numbers for
every claim it makes, and quote one of those lines exactly. The code then checks
that the quote is really on the line the agent cited.
"""

__version__ = "0.1.0"
