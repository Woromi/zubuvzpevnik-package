strokeUp = \markup { 
  \combine
  \override #'(thickness . 1.3) 
  \draw-line #'(0 . 2)\raise #2 
  \arrow-head #Y #UP ##f
}
strokeDown = \markup { 
  \combine
  \arrow-head #Y #DOWN ##f 
  \override #'(thickness . 1.3) 
  \draw-line #'(0 . 2)
}

\layout {
  \context {
    \ChordNames {
      \set chordChanges = ##t
      \override ChordName.font-series = #'bold
    }
  }
  \context {
    \TabStaff {
      % Ultimate guitar style
      \stemDown
      \override Beam.concaveness = #10000 % Horizontal beams
      \override Beam.positions = #'(-5 . -5) % All at the same position
    }
  }
}
