
import os
 
workers = 2
worker_class = "sync"
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
timeout = 120
keepalive = 5
 