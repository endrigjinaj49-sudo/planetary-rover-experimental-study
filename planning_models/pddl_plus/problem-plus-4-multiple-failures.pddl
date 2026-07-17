(define (problem memory-rover-plus-multiple-failures)
  (:domain memory-rover-plus)

  (:objects
    rover1 - rover
    base site1 site2 site3 - location
    data1 data2 data3 data4 - data
  )

  (:init
    (at rover1 base)

    (base base)

    ;; Linear exploration route
    (connected base site1)
    (connected site1 base)

    (connected site1 site2)
    (connected site2 site1)

    (connected site2 site3)
    (connected site3 site2)

    ;; Data locations
    (data-at data1 site1)
    (data-at data2 site1)
    (data-at data3 site2)
    (data-at data4 site3)

    ;; Rover memory
    (= (used-memory rover1) 0)
    (= (memory-capacity rover1) 10)

    ;; data1: safe
    (= (data-size data1) 4)

    (= (corruption data1) 0)
    (= (corruption-limit data1) 8)
    (= (corruption-rate data1) 0.5)

    (= (encoding-progress data1) 0)
    (= (encoding-required data1) 4)
    (= (encoding-rate data1) 2)

    ;; data2: safe
    (= (data-size data2) 6)

    (= (corruption data2) 0)
    (= (corruption-limit data2) 6)
    (= (corruption-rate data2) 1)

    (= (encoding-progress data2) 0)
    (= (encoding-required data2) 3)
    (= (encoding-rate data2) 1)

    ;; data3: fails because corruption is too fast
    (= (data-size data3) 5)

    (= (corruption data3) 0)
    (= (corruption-limit data3) 2)
    (= (corruption-rate data3) 2)

    (= (encoding-progress data3) 0)
    (= (encoding-required data3) 4)
    (= (encoding-rate data3) 1)

    ;; data4: fails because encoding is too slow
    (= (data-size data4) 5)

    (= (corruption data4) 0)
    (= (corruption-limit data4) 3)
    (= (corruption-rate data4) 1)

    (= (encoding-progress data4) 0)
    (= (encoding-required data4) 5)
    (= (encoding-rate data4) 0.5)
  )

  (:goal
    (and
      (offloaded data1)
      (offloaded data2)
      (offloaded data3)
      (offloaded data4)

      (not (lost data1))
      (not (lost data2))
      (not (lost data3))
      (not (lost data4))
    )
  )

  (:metric minimize (total-time))
)