import time

class Bot(object):
    def __init__(self, s, nickname, username, realname):
        self.nickname = nickname
        self.username = username
        self.realname = realname
        self.socket = s
        self.write_buffer = b""
        self.read_buffer = b""
        self.last_read = None
        self.ping_sent = False
        self._channels = []
        self.last_status = 0

    def fileno(self):
        return self.socket.fileno()

    def queue_send(self, data):
        encoded_data = data.encode("utf8")
        self.write_buffer += encoded_data + b"\r\n"

    def send(self):
        self.write_buffer = self.write_buffer[self.socket.send(self.write_buffer):]

    def waiting_send(self):
        return bool(len(self.write_buffer))

    def read(self):
        data = b""
        try:
            data = self.read_buffer+self.socket.recv(2048)
        except:
            return []
        self.read_buffer = b""
        data_lines = [line.strip(b"\r") for line in data.split(b"\n")]

        if data_lines[-1]:
            self.read_buffer = data_lines[-1]
        data_lines.pop(-1)

        decoded_lines = []
        for line in data_lines:
            try:
                line = line.decode("utf8")
            except:
                try:
                    line = line.decode("latin-1")
                except:
                    continue
            decoded_lines.append(line)
        self.last_read = time.time()
        self.ping_sent = False
        return decoded_lines

    def identify(self):
        self.send_identify(self.nickname, self.username, self.realname)

    def send_identify(self, nickname, username, realname):
        self.send_nick(nickname)
        self.send_user(username, realname)

    def send_ping(self, text="hello"):
        self.queue_send("PING :{0}".format(text))
        self.ping_sent = True

    def send_pong(self, text):
        self.queue_send("PONG :{0}".format(text))

    def send_privmsg(self, target, text):
        self.queue_send("PRIVMSG {0} :{1}".format(target,text))

    def send_join(self, target):
        self.queue_send("JOIN :{0}".format(target))

    def send_quit(self, text):
        self.queue_send("QUIT :{0}".format(text))

    def send_nick(self, nick):
        self.queue_send("NICK :{}".format(nick))

    def send_user(self, ident, real_name):
        self.queue_send("USER {} - - {}".format(ident, real_name))

    def send_who(self, channel):
        self.queue_send("WHO {}".format(channel))

    def is_own_nickname(self, nickname):
        return self.nickname==nickname

    def add_channel(self, channel):
        self._channels.append(channel)

    def remove_channel(self, channel):
        if channel in self._channels:
            self._channels.remove(channel)

    def summary(self):
        return "<{} ({}): {}>".format(self.nickname, self.last_status, ", ".join(self._channels))
