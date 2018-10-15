#!/usr/bin/env python3

import sys
import doodle

if __name__ == '__main__':
    debug = len(sys.argv) > 1 and sys.argv[1] == '--debug'
    doodle.init_db()
    doodle.get_app().run(debug=debug)
