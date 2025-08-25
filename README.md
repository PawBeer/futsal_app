Create a file with installed libraries (packages) for the project:
```bash
pip freeze > requirements.txt
```

Installing Python libraries from a requirements file:
```bash
pip install -r requirements.txt
```

Application description:

The purpose of the Futsal App is to manage games taking place on a specific date, in which 10 players participate. 
Each game has a date, status, description, and list of players. The players are divided into two groups (permanent and reserved) in game. Players can confirm their attendance or absence by clicking a individual checkbox. 
Information about a player's status change, along with the date of the change, is stored in BookingHistory, and based on this entry, the application assigns the opportunity to play (in order).
The app also has a list of all the players who have signed up. When signing up, players give their first name, last name, email, and mobile number.
The admin (superuser) manages the entire team. They can add/edit players and add/remove/edit games.
