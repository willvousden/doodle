#!/usr/bin/env python3

import sys
import doodle

if __name__ == '__main__':
    db_path = 'doodle.db'
    debug = len(sys.argv) > 1 and sys.argv[1] == '--debug'
    doodle.init_db(db_path)
    doodle.get_app(db_path).run(debug=debug)
