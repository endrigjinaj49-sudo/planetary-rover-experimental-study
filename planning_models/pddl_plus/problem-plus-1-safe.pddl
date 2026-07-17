(define (problem memory-rover-plus-safe)
  (:domain memory-rover-plus)

  (:objects
    rover1 - rover
    base site1 - location
    data1 - data
  )

  (:init
    (at rover1 base)

    (base base)

    (connected base site1)
    (connected site1 base)

    (data-at data1 site1)

    (= (used-memory rover1) 0)
    (= (memory-capacity rover1) 10)

    (= (data-size data1) 4)

    (= (corruption data1) 0)
    (= (corruption-limit data1) 10)
    (= (corruption-rate data1) 1)

    (= (encoding-progress data1) 0)
    (= (encoding-required data1) 2)
    (= (encoding-rate data1) 1)
  )

  (:goal
    (and
      (offloaded data1)
      (not (lost data1))
    )
  )

  (:metric minimize (total-time))
)