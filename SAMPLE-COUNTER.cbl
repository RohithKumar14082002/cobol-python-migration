       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE-COUNTER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9 VALUE ZERO.
       PROCEDURE DIVISION.
           DISPLAY "Counting from 1 to 3:"
           PERFORM UNTIL WS-COUNT >= 3
               ADD 1 TO WS-COUNT
               DISPLAY WS-COUNT
           END-PERFORM
           STOP RUN.