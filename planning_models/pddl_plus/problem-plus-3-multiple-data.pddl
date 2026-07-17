(define (problem memory-rover-plus-multiple-data)
  (:domain memory-rover-plus)

  (:objects
    rover1 - rover
    base site1 site2 - location
    data1 data2 data3 - data
  )

  (:init
    (at rover1 base)

    (base base)

    (connected base site1)
    (connected site1 base)

    (connected site1 site2)
    (connected site2 site1)

    (data-at data1 site1)
    (data-at data2 site1)
    (data-at data3 site2)

    (= (used-memory rover1) 0)
    (= (memory-capacity rover1) 10)

    (= (data-size data1) 4)
    (= (data-size data2) 6)
    (= (data-size data3) 5)

    ;; data1: fast encoding and slow corruption
    (= (corruption data1) 0)
    (= (corruption-limit data1) 8)
    (= (corruption-rate data1) 0.5)

    (= (encoding-progress data1) 0)
    (= (encoding-required data1) 4)
    (= (encoding-rate data1) 2)

    ;; data2: slower encoding and moderate corruption
    (= (corruption data2) 0)
    (= (corruption-limit data2) 6)
    (= (corruption-rate data2) 1)

    (= (encoding-progress data2) 0)
    (= (encoding-required data2) 3)
    (= (encoding-rate data2) 1)

    ;; data3: urgent, with fast corruption
    (= (corruption data3) 0)
    (= (corruption-limit data3) 2)
    (= (corruption-rate data3) 1.5)

    (= (encoding-progress data3) 0)
    (= (encoding-required data3) 1)
    (= (encoding-rate data3) 1)
  )

  (:goal
    (and
      (offloaded data1)
      (offloaded data2)
      (offloaded data3)

      (not (lost data1))
      (not (lost data2))
      (not (lost data3))
    )
  )

  (:metric minimize (total-time))
)