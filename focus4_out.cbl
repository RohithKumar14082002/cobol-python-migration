       IDENTIFICATION DIVISION.
       PROGRAM-ID. EXCEL-REPORT-GEN.
       AUTHOR. FOCUS-TO-COBOL-CONVERTER.
      *******************************************************************
      * PROGRAM TO READ INPUT FILE AND GENERATE EXCEL REPORT            *
      * CONVERTED FROM FOCUS                                            *
      *******************************************************************
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MAINFILE ASSIGN TO MAINFILE
           ORGANIZATION IS INDEXED
           ACCESS MODE IS SEQUENTIAL
           RECORD KEY IS MAIN-KEY
           FILE STATUS IS MAINFILE-STATUS.
           
           SELECT OUTFILE ASSIGN TO OUTFILE
           ORGANIZATION IS SEQUENTIAL
           ACCESS MODE IS SEQUENTIAL
           FILE STATUS IS OUTFILE-STATUS.
       
       DATA DIVISION.
       FILE SECTION.
       FD  MAINFILE.
       01  MAINFILE-RECORD.
           05  MAIN-KEY                PIC X(10).
           05  AMOUNT                  PIC S9(11)V99 COMP-3.
           05  PROD-TYPE               PIC X(20).
           05  FILLER                  PIC X(100).
           
       FD  OUTFILE.
       01  OUTFILE-RECORD              PIC X(1024).
       
       WORKING-STORAGE SECTION.
       01  FILE-STATUS-CODES.
           05  MAINFILE-STATUS         PIC X(2) VALUE SPACES.
           05  OUTFILE-STATUS          PIC X(2) VALUE SPACES.
           
       01  PROGRAM-SWITCHES.
           05  EOF-SWITCH              PIC X VALUE 'N'.
               88  END-OF-FILE         VALUE 'Y'.
           05  RECORD-FOUND-SW         PIC X VALUE 'N'.
               88  RECORD-FOUND        VALUE 'Y'.
           05  ERROR-FOUND-SW          PIC X VALUE 'N'.
               88  ERROR-FOUND         VALUE 'Y'.
               
       01  COUNTERS.
           05  RECORD-COUNTER          PIC 9(9) VALUE ZERO.
           05  UNIQUE-GROUP-COUNT      PIC 9(9) VALUE ZERO.
           
       01  WS-VARIABLES.
           05  WS-DESCRIPTION          PIC X(30) VALUE 'ELECTRONICS'.
           05  WS-PROD-CNT             PIC S9(13)V99 COMP-3 VALUE 1.
           
       01  SUMMARY-TABLE.
           05  SUMMARY-ENTRY OCCURS 1000 TIMES
               INDEXED BY SUMMARY-IDX SEARCH-IDX.
               10  SUMMARY-DESCRIPTION PIC X(30).
               10  SUMMARY-PROD-TYPE   PIC X(20).
               10  SUMMARY-AMOUNT      PIC S9(13)V99 COMP-3.
               10  SUMMARY-PROD-CNT    PIC S9(13)V99 COMP-3.
               10  SUMMARY-USED        PIC X VALUE 'N'.
                   88 SUMMARY-IS-USED  VALUE 'Y'.
               
       01  EXCEL-HEADER-1.
           05  FILLER                  PIC X(14) VALUE 'SUMMARY_REPORT'.
           
       01  EXCEL-HEADER-2.
           05  FILLER                  PIC X(30) VALUE 'DESCRIPTION'.
           05  FILLER                  PIC X(1)  VALUE ','.
           05  FILLER                  PIC X(20) VALUE 'PROD_TYPE'.
           05  FILLER                  PIC X(1)  VALUE ','.
           05  FILLER                  PIC X(10) VALUE 'AMOUNT'.
           05  FILLER                  PIC X(1)  VALUE ','.
           05  FILLER                  PIC X(13) VALUE 'PRODUCT_COUNT'.
           
       01  EXCEL-DETAIL.
           05  EXCEL-DESCRIPTION       PIC X(30).
           05  FILLER                  PIC X(1)  VALUE ','.
           05  EXCEL-PROD-TYPE         PIC X(20).
           05  FILLER                  PIC X(1)  VALUE ','.
           05  EXCEL-AMOUNT            PIC -Z(10)9.99.
           05  FILLER                  PIC X(1)  VALUE ','.
           05  EXCEL-PROD-CNT          PIC -Z(12)9.99.
           
       01  EXCEL-STYLE-INFO.
           05  FILLER PIC X(80) VALUE 
              '<style type="text/css">'.
           05  FILLER PIC X(80) VALUE 
              'table {border-collapse: collapse; font-family: Arial;'.
           05  FILLER PIC X(80) VALUE 
              'font-size: 10pt;}'.
           05  FILLER PIC X(80) VALUE 
              'th {background-color: blue; color: white;'.
           05  FILLER PIC X(80) VALUE 
              'font-weight: bold; text-align: center;}'.
           05  FILLER PIC X(80) VALUE 
              'td, th {border: 1px solid black; padding: 5px;}'.
           05  FILLER PIC X(80) VALUE 
              '</style>'.
           
       PROCEDURE DIVISION.
       0000-MAIN-PROCESS.
           PERFORM 1000-INITIALIZATION
           
           IF NOT ERROR-FOUND
               PERFORM 2000-PROCESS-DATA
               
               IF RECORD-FOUND
                   PERFORM 3000-GENERATE-EXCEL
                   
                   IF ERROR-FOUND
                       MOVE 999 TO RETURN-CODE
                   END-IF
               ELSE
                   DISPLAY 'NO RECORDS FOUND IN MAINFILE'
                   MOVE 999 TO RETURN-CODE
               END-IF
           ELSE
               MOVE 999 TO RETURN-CODE
           END-IF
           
           PERFORM 9000-TERMINATION
           
           GOBACK.
           
       1000-INITIALIZATION.
           INITIALIZE SUMMARY-TABLE
           INITIALIZE COUNTERS
           
           OPEN INPUT MAINFILE
           
           IF MAINFILE-STATUS NOT = '00'
               DISPLAY 'ERROR OPENING MAINFILE: ' MAINFILE-STATUS
               MOVE 'Y' TO ERROR-FOUND-SW
           END-IF.
           
       2000-PROCESS-DATA.
           READ MAINFILE
               AT END
                   MOVE 'Y' TO EOF-SWITCH
               NOT AT END
                   ADD 1 TO RECORD-COUNTER
                   MOVE 'Y' TO RECORD-FOUND-SW
           END-READ
           
           PERFORM UNTIL END-OF-FILE
               PERFORM 2100-AGGREGATE-DATA
               
               READ MAINFILE
                   AT END
                       MOVE 'Y' TO EOF-SWITCH
                   NOT AT END
                       ADD 1 TO RECORD-COUNTER
               END-READ
           END-PERFORM.
           
       2100-AGGREGATE-DATA.
      *    Search for existing group with same DESCRIPTION and PROD-TYPE
           MOVE 'N' TO RECORD-FOUND-SW
           
           PERFORM VARYING SEARCH-IDX FROM 1 BY 1
               UNTIL SEARCH-IDX > UNIQUE-GROUP-COUNT
                  OR RECORD-FOUND
               
               IF SUMMARY-DESCRIPTION(SEARCH-IDX) = WS-DESCRIPTION
                  AND SUMMARY-PROD-TYPE(SEARCH-IDX) = PROD-TYPE
                   MOVE 'Y' TO RECORD-FOUND-SW
               END-IF
           END-PERFORM
           
           IF RECORD-FOUND
      *        Add to existing group
               COMPUTE SUMMARY-AMOUNT(SEARCH-IDX) = 
                   SUMMARY-AMOUNT(SEARCH-IDX) + AMOUNT
               COMPUTE SUMMARY-PROD-CNT(SEARCH-IDX) = 
                   SUMMARY-PROD-CNT(SEARCH-IDX) + WS-PROD-CNT
           ELSE
      *        Create new group
               ADD 1 TO UNIQUE-GROUP-COUNT
               
               IF UNIQUE-GROUP-COUNT > 1000
                   DISPLAY 'ERROR: SUMMARY TABLE OVERFLOW'
                   MOVE 'Y' TO ERROR-FOUND-SW
                   MOVE 'Y' TO EOF-SWITCH
               ELSE
                   MOVE WS-DESCRIPTION TO 
                       SUMMARY-DESCRIPTION(UNIQUE-GROUP-COUNT)
                   MOVE PROD-TYPE TO 
                       SUMMARY-PROD-TYPE(UNIQUE-GROUP-COUNT)
                   MOVE AMOUNT TO 
                       SUMMARY-AMOUNT(UNIQUE-GROUP-COUNT)
                   MOVE WS-PROD-CNT TO 
                       SUMMARY-PROD-CNT(UNIQUE-GROUP-COUNT)
                   MOVE 'Y' TO 
                       SUMMARY-USED(UNIQUE-GROUP-COUNT)
               END-IF
           END-IF.
           
       3000-GENERATE-EXCEL.
           OPEN OUTPUT OUTFILE
           
           IF OUTFILE-STATUS NOT = '00'
               DISPLAY 'ERROR OPENING OUTFILE: ' OUTFILE-STATUS
               MOVE 'Y' TO ERROR-FOUND-SW
               GO TO 3000-EXIT
           END-IF
           
      *    Write HTML header with styling for Excel
           WRITE OUTFILE-RECORD FROM 
               '<html xmlns:o="urn:schemas-microsoft-com:office:office"'
           WRITE OUTFILE-RECORD FROM 
               'xmlns:x="urn:schemas-microsoft-com:office:excel"'
           WRITE OUTFILE-RECORD FROM 
               'xmlns="http://www.w3.org/TR/REC-html40">'
           WRITE OUTFILE-RECORD FROM '<head>'
           WRITE OUTFILE-RECORD FROM 
               '<meta http-equiv=Content-Type content="text/html; '
               & 'charset=utf-8">'
           WRITE OUTFILE-RECORD FROM EXCEL-STYLE-INFO
           WRITE OUTFILE-RECORD FROM '</head>'
           WRITE OUTFILE-RECORD FROM '<body>'
           
      *    Write title
           WRITE OUTFILE-RECORD FROM 
               '<h2 style="color:blue;font-family:Arial;">SUMMARY_REPORT'
               & '</h2>'
           
      *    Start table
           WRITE OUTFILE-RECORD FROM '<table>'
           
      *    Write header row
           WRITE OUTFILE-RECORD FROM '<tr>'
           WRITE OUTFILE-RECORD FROM '<th>DESCRIPTION</th>'
           WRITE OUTFILE-RECORD FROM '<th>PROD_TYPE</th>'
           WRITE OUTFILE-RECORD FROM '<th>AMOUNT</th>'
           WRITE OUTFILE-RECORD FROM '<th>PRODUCT_COUNT</th>'
           WRITE OUTFILE-RECORD FROM '</tr>'
           
      *    Write data rows
           PERFORM VARYING SUMMARY-IDX FROM 1 BY 1
               UNTIL SUMMARY-IDX > UNIQUE-GROUP-COUNT
               
               IF SUMMARY-IS-USED(SUMMARY-IDX)
                   MOVE SUMMARY-DESCRIPTION(SUMMARY-IDX) TO 
                       EXCEL-DESCRIPTION
                   MOVE SUMMARY-PROD-TYPE(SUMMARY-IDX) TO 
                       EXCEL-PROD-TYPE
                   MOVE SUMMARY-AMOUNT(SUMMARY-IDX) TO 
                       EXCEL-AMOUNT
                   MOVE SUMMARY-PROD-CNT(SUMMARY-IDX) TO 
                       EXCEL-PROD-CNT
                   
                   WRITE OUTFILE-RECORD FROM '<tr>'
                   STRING '<td>' EXCEL-DESCRIPTION '</td>'
                       INTO OUTFILE-RECORD
                   WRITE OUTFILE-RECORD
                   STRING '<td>' EXCEL-PROD-TYPE '</td>'
                       INTO OUTFILE-RECORD
                   WRITE OUTFILE-RECORD
                   STRING '<td align="right">' EXCEL-AMOUNT '</td>'
                       INTO OUTFILE-RECORD
                   WRITE OUTFILE-RECORD
                   STRING '<td align="right">' EXCEL-PROD-CNT '</td>'
                       INTO OUTFILE-RECORD
                   WRITE OUTFILE-RECORD
                   WRITE OUTFILE-RECORD FROM '</tr>'
               END-IF
           END-PERFORM
           
      *    End table and HTML
           WRITE OUTFILE-RECORD FROM '</table>'
           WRITE OUTFILE-RECORD FROM '</body>'
           WRITE OUTFILE-RECORD FROM '</html>'
           
           CLOSE OUTFILE
           
           IF OUTFILE-STATUS NOT = '00'
               DISPLAY 'ERROR CLOSING OUTFILE: ' OUTFILE-STATUS
               MOVE 'Y' TO ERROR-FOUND-SW
           END-IF
           
           IF UNIQUE-GROUP-COUNT = 0
               DISPLAY 'NO RECORDS FOUND FOR REPORT'
               MOVE 'Y' TO ERROR-FOUND-SW
           ELSE
               DISPLAY 'REPORT GENERATED SUCCESSFULLY WITH ' 
                   UNIQUE-GROUP-COUNT ' RECORDS'
           END-IF.
           
       3000-EXIT.
           EXIT.
           
       9000-TERMINATION.
           IF MAINFILE-STATUS NOT = '00' AND MAINFILE-STATUS NOT = '97'
               CLOSE MAINFILE
           END-IF.