class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'    #yellow
    FAIL = '\033[91m'       #red
    GREY = '\033[90m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_color(s, color=bcolors.OKGREEN):
    print(color + s + bcolors.ENDC)

def print_err(s):
    print_color(s, bcolors.FAIL)
    