1. PLAYER
   - ID (PK)
   - name
   - surname 
   - email 
   - mobile_no
   - nickname
   - role(perme, ac)


2. PLAYER_STATUS (lub ENUM)
   - planned
   - rejected
   - confirmed


3. PLAYER_ROLE (lub ENUM)
   - permanent
   - temporary 
   - substitute


4. PLAYER_ROLE_ASSIGNMENT
   - type (FK:  PLAYER_ROLE)
   - substitutes_for (FK: PLAYER)
   - from : date
   - to : date 


5. GAME_STATUS (lub ENUM)
   - planned
   - played
   - canceled


6. GAME
   - ID (PK)
   - status (FK: GAME_STATUS) 
   - when : date
   - description: text


7. BOOKING_HISTORY_FOR_GAME
   - game_id (FK: GAME)
   - player_id (FK: PLAYER)
   - status (FK: PLAYER_STATUS)
   - when : datetime
