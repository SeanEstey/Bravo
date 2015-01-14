import os
os.chdir('/root/bravo')

import bravo

bravo.set_mode('deploy')
bravo.run_scheduler()
