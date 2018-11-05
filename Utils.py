def remove_colon(s):
    if s.startswith(":"):
        s = s[1:]
    return s

def separate_hostmask(hostmask):
    hostmask = remove_colon(hostmask)
    first_delim = hostmask.find("!")
    second_delim = hostmask.find("@")
    nickname = username = hostname = hostmask
    if first_delim > -1 and second_delim > first_delim:
        nickname, username = hostmask.split("!", 1)
        username, hostname = hostmask.split("@", 1)
    return nickname, username, hostname
