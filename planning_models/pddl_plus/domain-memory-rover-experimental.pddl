(define (domain memory-rover-experimental)

  (:requirements
    :strips
    :typing
    :negative-preconditions
    :fluents
    :time
  )

  (:types
    rover
    location
    data
  )

  (:predicates

    ;; Rover and map state
    (at ?r - rover ?l - location)
    (connected ?from ?to - location)
    (base ?l - location)

    ;; Timed movement state
    (travelling ?r - rover)
    (moving ?r - rover ?from ?to - location)

    ;; Data source
    (data-at ?d - data ?l - location)

    ;; Data lifecycle
    (collected ?d - data)
    (stored ?d - data)
    (stored-by ?d - data ?r - rover)
    (encoded ?d - data)
    (offloaded ?d - data)
    (lost ?d - data)
  )

  (:functions

    ;; Rover memory
    (used-memory ?r - rover)
    (memory-capacity ?r - rover)

    ;; Timed movement
    (travel-progress ?r - rover)
    (travel-time ?from ?to - location)

    ;; Dataset storage requirement
    (data-size ?d - data)

    ;; Corruption model
    (corruption ?d - data)
    (corruption-limit ?d - data)
    (corruption-rate ?d - data)

    ;; Encoding model
    (encoding-progress ?d - data)
    (encoding-required ?d - data)
    (encoding-rate ?d - data)
  )

  ;; The planner chooses when and where to begin travelling.
  (:action start-move
    :parameters (
      ?r - rover
      ?from - location
      ?to - location
    )

    :precondition (and
      (at ?r ?from)
      (connected ?from ?to)
      (not (travelling ?r))
    )

    :effect (and
      (not (at ?r ?from))
      (travelling ?r)
      (moving ?r ?from ?to)
      (assign (travel-progress ?r) 0)
    )
  )

  ;; Travel progress increases automatically while the rover is moving.
  (:process rover-travel
    :parameters (
      ?r - rover
      ?from - location
      ?to - location
    )

    :precondition (and
      (travelling ?r)
      (moving ?r ?from ?to)
    )

    :effect
      (increase
        (travel-progress ?r)
        (* #t 1)
      )
  )

  ;; Arrival occurs automatically when the required travel time is reached.
  (:event arrive
    :parameters (
      ?r - rover
      ?from - location
      ?to - location
    )

    :precondition (and
      (travelling ?r)
      (moving ?r ?from ?to)
      (>=
        (travel-progress ?r)
        (travel-time ?from ?to)
      )
    )

    :effect (and
      (at ?r ?to)
      (not (travelling ?r))
      (not (moving ?r ?from ?to))
      (assign (travel-progress ?r) 0)
    )
  )

  (:action collect-data
    :parameters (
      ?r - rover
      ?d - data
      ?l - location
    )

    :precondition (and
      (at ?r ?l)
      (data-at ?d ?l)
      (not (collected ?d))
      (not (stored ?d))
      (not (offloaded ?d))
      (not (lost ?d))
      (>=
        (memory-capacity ?r)
        (+ (used-memory ?r) (data-size ?d))
      )
    )

    :effect (and
      (collected ?d)
      (stored ?d)
      (stored-by ?d ?r)
      (increase
        (used-memory ?r)
        (data-size ?d)
      )
    )
  )

  (:action offload-data
    :parameters (
      ?r - rover
      ?d - data
      ?l - location
    )

    :precondition (and
      (at ?r ?l)
      (base ?l)
      (stored ?d)
      (stored-by ?d ?r)
      (encoded ?d)
      (not (offloaded ?d))
      (not (lost ?d))
    )

    :effect (and
      (offloaded ?d)
      (not (stored ?d))
      (not (stored-by ?d ?r))
      (decrease
        (used-memory ?r)
        (data-size ?d)
      )
    )
  )

  (:process memory-corruption
    :parameters (
      ?d - data
    )

    :precondition (and
      (stored ?d)
      (not (offloaded ?d))
      (not (lost ?d))
    )

    :effect
      (increase
        (corruption ?d)
        (* #t (corruption-rate ?d))
      )
  )

  (:process data-encoding
    :parameters (
      ?d - data
    )

    :precondition (and
      (stored ?d)
      (not (encoded ?d))
      (not (offloaded ?d))
      (not (lost ?d))
    )

    :effect
      (increase
        (encoding-progress ?d)
        (* #t (encoding-rate ?d))
      )
  )

  (:event encoding-complete
    :parameters (
      ?d - data
    )

    :precondition (and
      (stored ?d)
      (not (encoded ?d))
      (not (lost ?d))
      (>=
        (encoding-progress ?d)
        (encoding-required ?d)
      )
    )

    :effect
      (encoded ?d)
  )

  (:event data-loss
    :parameters (
      ?d - data
      ?r - rover
    )

    :precondition (and
      (stored ?d)
      (stored-by ?d ?r)
      (not (offloaded ?d))
      (not (lost ?d))
      (>=
        (corruption ?d)
        (corruption-limit ?d)
      )
    )

    :effect (and
      (lost ?d)
      (not (stored ?d))
      (not (stored-by ?d ?r))
      (decrease
        (used-memory ?r)
        (data-size ?d)
      )
    )
  )
)
