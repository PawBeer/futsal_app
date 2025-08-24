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
   
   - slot_1 : player_id
   - slot_2 : player_id
   - slot_3 : player_id
   - slot_4 : player_id
   - slot_5 : player_id 
   - slot_6 : player_id
   - slot_7 : player_id
   - slot_8 : player_id
   - slot_9 : player_id
   - slot_10 : player_id


7. BOOKING_HISTORY_FOR_GAME
   - game_id (FK: GAME)
   - player_id (FK: PLAYER)
   - status (FK: PLAYER_STATUS)
   - when : datetime