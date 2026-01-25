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
  ragged-right = ##f % Even short tabs would be spread across the whole page

  \context {
    \ChordNames {
      \set chordChanges = ##t
      \override ChordName.font-series = #'bold
      \override ChordName.font-size = #0
    }
  }
  
  \context {
    \TabStaff {
      % Ultimate guitar style
      \stemDown
      \override Beam.concaveness = #10000 % Horizontal beams
      \override Beam.positions = #'(-5 . -5) % All at the same position
      
      \set TabStaff.stringTunings = #guitar-tuning
    }
  }
}
