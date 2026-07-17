(define (domain memory-rover)
  (:requirements :strips :typing :negative-preconditions :fluents)

  (:types
    rover location data
  )

  (:predicates
    (at ?r - rover ?l - location)
    (connected ?from ?to - location)
    (base ?l - location)
    (data-at ?d - data ?l - location)
    (collected ?d - data)
    (stored ?d - data)
    (offloaded ?d - data)
  )

  (:functions
    (used-memory ?r - rover)
    (memory-capacity ?r - rover)
    (data-size ?d - data)
  )

  (:action move
    :parameters (?r - rover ?from ?to - location)
    :precondition (and
      (at ?r ?from)
      (connected ?from ?to)
    )
    :effect (and
      (not (at ?r ?from))
      (at ?r ?to)
    )
  )

  (:action collect-data
    :parameters (?r - rover ?d - data ?l - location)
    :precondition (and
      (at ?r ?l)
      (data-at ?d ?l)
      (not (collected ?d))
      (>= (memory-capacity ?r)
          (+ (used-memory ?r) (data-size ?d)))
    )
    :effect (and
      (collected ?d)
      (stored ?d)
      (increase (used-memory ?r) (data-size ?d))
    )
  )

  (:action offload-data
    :parameters (?r - rover ?d - data ?l - location)
    :precondition (and
      (at ?r ?l)
      (base ?l)
      (stored ?d)
    )
    :effect (and
      (offloaded ?d)
      (not (stored ?d))
      (decrease (used-memory ?r) (data-size ?d))
    )
  )
)