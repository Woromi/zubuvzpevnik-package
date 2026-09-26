\version "2.24.1"

strokeUp = \markup\combine\override #'(thickness . 1.3) \draw-line #'(0 . 2)\raise #2 \arrow-head #Y #UP ##f
strokeDown = \markup\combine\arrow-head #Y #DOWN ##f \override #'(thickness . 1.3) \draw-line #'(0 . 2)

% Tab stems in the tablature-site style: every stem starts just below the
% staff and is the same length, ending where the beams sit (docs/internals.md).
% \tabFullNotation reverts Stem.length, so the overrides ride along with it.
% Grace notes stand outside the rhythm, so they get no stem, flag or beam.
#(define (zub-grace? grob)
   (not (zero? (ly:moment-grace (grob::when grob)))))
#(define (zub-unless-grace print)
   (lambda (grob) (if (zub-grace? grob) #f (print grob))))
#(define (zub-tab-stem grob)
   ;; Beamed stems ignore stem-begin-position, so cut them off below the staff.
   (let ((st (if (zub-grace? grob) #f (tabvoice::draw-double-stem-for-half-notes grob))))
     (if (and (ly:stencil? st) (ly:grob? (ly:grob-object grob 'beam #f)))
         (let ((top (* -3 (ly:staff-symbol-staff-space grob)))
               (y (ly:stencil-extent st Y)))
           (ly:round-filled-box (ly:stencil-extent st X)
                                (cons (car y) (min (cdr y) top)) 0))
         st)))
zubTabFullNotation = \tabFullNotation
tabFullNotation = {
  \zubTabFullNotation
  \override TabStaff.Stem.stem-begin-position = #-6
  \override TabStaff.Stem.length = #4
  \override TabStaff.Stem.stencil = #zub-tab-stem
  \override TabStaff.Flag.stencil = #(zub-unless-grace ly:flag::print)
  \override TabStaff.Beam.stencil = #(zub-unless-grace ly:beam::print)
}

\layout {
  ragged-right = ##f % Even short tabs would be spread across the whole page

  \context {
    \Staff {
      \set Score.proportionalNotationDuration = #(ly:make-moment 1/8)
    }
  }

  \context {
    \ChordNames {
      % H and B when the fragment is parsed in German note names, B and Bb
      % otherwise. Bass notes are left to fall back to this namer: \germanChords
      % would spell them "G/h"; the book prints G/H.
      \set chordRootNamer = #(if (assq 'h pitchnames)
                                 (chord-name->german-markup #t)
                                 note-name->markup)
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
