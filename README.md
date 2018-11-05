# CobaltLongclaw
A event-driven python3 IRC bot, capable of maintaining hundreds of simultaneous connections through Tor or a list of SOCKS proxies,
with an interactive IPython shell for manipulation.

CobaltLongclaw's event system is derived from that of [Bitbot](https://github.com/jesopo/bitbot), the primary difference being the
use of '/' as a separator for events

## Dependencies
* [Pysocks](https://pypi.org/project/PySocks/)
* [stem](https://pypi.org/project/stem/)
* [IPython](https://pypi.org/project/ipython/)

Use `pip3 install -r requirements.txt` to install them all at once.

## Using CobaltLongclaw
```
./shell.py -n 10 irc.example.com 6667
In [1]: bot_manager.events.single("received/numeric/001").hook(lambda event: event["bot"].send_join("#Botchannel"))
In [2]: client_factory.start()
```
