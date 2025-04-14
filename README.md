# CfMafiaBot
Based on Niklex21's project [MafiaBot](https://github.com/Niklex21/MafiaBot/)

This bot hosts Mafia games inside telegram. The twist is that every day players receive a task from https://codeforces.com. They must solve it in daytime in order to continue playing.
## Installation

* Install [Python](https://www.python.org/downloads) version no less than 3.12.0
* Clone repository:    
```shell
git clone https://github.com/SuperMeatBoyCoder/CfMafiaBot
cd CfMafiaBot
```
* Install requirements:
```shell
pip install -r requirements.txt
```
* Add file ```bot_token.py```:
```shell
touch bot_token.py
echo "BOT_TOKEN = <TOKEN>" >> bot_token.py
```
(replacing ```<TOKEN>``` with token of your bot)
* Start bot:  
```shell
python bot.py
```
