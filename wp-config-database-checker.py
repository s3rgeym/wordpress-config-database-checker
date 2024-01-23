#!/usr/bin/env python
"""
Example:
    fd 'wp-config\.php' dump | python wp-config-database-checker.py -D
"""
import argparse
import multiprocessing
import re
import shlex
import sys
from functools import partial
from itertools import repeat
from pathlib import Path

# pip install mysql-connector-python
from mysql import connector

CLEAR = "\x1b[m"
BLACK = "\x1b[30m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
PURPLE = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"

DEFINE_DB_RE = re.compile(
    r"""define\(\s*['"](?P<key>DB_.+?)['"]\s*,\s*['"](?P<value>[^'"]+)"""
)

print_err = partial(print, file=sys.stderr)


def check_connection(config_file, connection_timeout):
    with open(config_file, "r") as f:
        contents = f.read()
    db_config = {
        m.group("key"): m.group("value")
        for m in DEFINE_DB_RE.finditer(contents)
    }
    hostname = db_config.get("DB_HOST", "localhost")
    try:
        # https://www.inmotionhosting.com/support/edu/wordpress/change-database-port-wordpress/
        hostname, port = hostname.rsplit(":", 1)
        port = int(port)
    except ValueError:
        port = 3306

    if (
        hostname.lower()
        # Добавил некоторые имена
        in ["localhost", "127.0.0.1", "db", "database", "mysql"]
        and args.use_dirname_instead_of_localhost
    ):
        hostname = Path(config_file).resolve().parent.name
    username = db_config.get("DB_USER", "root")
    password = db_config.get("DB_PASSWORD", "")
    database = db_config.get("DB_NAME", "")

    # https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html
    success = False
    try:
        with connector.connect(
            user=username,
            password=password,
            host=hostname,
            database=database,
            connection_timeout=connection_timeout,
        ) as connenction:
            if connenction.is_connected():
                print(
                    "mysql --host=",
                    shlex.quote(hostname),
                    " -u",
                    shlex.quote(username),
                    " -p",
                    shlex.quote(password),
                    [f"--port={port}", ""][port == 3306],
                    " ",
                    shlex.quote(database),
                    sep="",
                )
                success = True
    except connector.Error as ex:
        print_err(f"{RED}{ex}{CLEAR}")

    result = [RED + "FAIL", GREEN + "PASS"][success]
    print_err(
        f"{CYAN}check {hostname=!r}, {username=!r}, {password=!r}, {database=!r}, {port=}: {result}{CLEAR}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="-", type=argparse.FileType())
    parser.add_argument(
        "-o", "--output", default="-", type=argparse.FileType("w")
    )
    parser.add_argument(
        "-t",
        "--connection-timeout",
        "--timeout",
        help="connection timeout in seconds (default: %(default)d)",
        type=int,
        default=15,
    )
    parser.add_argument(
        "-D",
        "--use-dirname-instead-of-localhost",
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "-p",
        "--processes",
        help="max number of processes",
        type=int,
        default=multiprocessing.cpu_count(),
    )
    args = parser.parse_args()

    print = partial(print, file=args.output, flush=True)

    with multiprocessing.Pool(args.processes) as pool:
        pool.starmap(
            check_connection,
            zip(
                filter(None, map(str.strip, args.input)),
                repeat(args.connection_timeout),
            ),
        )
