\include "zubuvzpevnik.ily"

#(define tw-fingerings
   '(
     ;; --- Lower Octave ---
     ((0 1 0)   . (one two three four five six)) ;; D4 (d')
     ((0 2 0)   . (one two three four five))     ;; E4 (e')
     ((0 3 1/2) . (one two three four))          ;; F#4 (fis')
     ((0 4 0)   . (one two three))               ;; G4 (g')
     ((0 5 0)   . (one two))                     ;; A4 (a')
     ((0 6 0)   . (one))                         ;; B4 (b')
     ((1 0 0)   . (    two three))               ;; C5 (c'') natural
     ((1 0 1/2) . ())                            ;; C#5 (cis'')

     ;; --- Higher Octave ---
     ((1 1 0)   . (    two three four five six)) ;; D5 (d'')
     ((1 2 0)   . (one two three four five))     ;; E5 (e'')
     ((1 3 1/2) . (one two three four))          ;; F#5 (fis'')
     ((1 4 0)   . (one two three))               ;; G5 (g'')
     ((1 5 0)   . (one two))                     ;; A5 (a'')
     ((1 6 0)   . (one))                         ;; B5 (b'')
     ((2 0 0)   . (    two three))               ;; C6 (c''') natural
     ((2 0 1/2) . ())                            ;; C#6 (cis''')
   ))

#(define (add-tw-fingering music)
   (music-map
     (lambda (m)
       (if (eq? (ly:music-property m 'name) 'NoteEvent)
           (let ((pitch (ly:music-property m 'pitch)))
             (if (ly:pitch? pitch)
                 (let* ((octave     (ly:pitch-octave pitch))
                        (notename   (ly:pitch-notename pitch))
                        (alteration (ly:pitch-alteration pitch))
                        (entry (assoc (list octave notename alteration) tw-fingerings)))
                   
                   (if entry
                       (let* ((holes (cdr entry))
                              (is-overblown (or (> octave 1) (and (= octave 1) (>= notename 1))))
                              
                              ;; 1. The diagram itself
                              (diagram-markup (markup #:override '(size . 0.6) #:woodwind-diagram 'tin-whistle `((cc . ,holes) (lh . ()) (rh . ()))))
                              
                              ;; 2. The visible plus sign
                              (plus-mark (markup #:fontsize 2 "+"))
                              
                              ;; 3. The invisible plus sign (takes up the exact same space)
                              (hidden-plus (markup #:transparent plus-mark))
                              
                              ;; THE FIX: 
                              ;; Now both overblown and normal notes have a 3-part column of identical height!
                              (final-markup (if is-overblown
                                                (markup #:override '(baseline-skip . 1.5) #:center-column (
                                                    diagram-markup
                                                    plus-mark 
                                                  ))
                                                (markup #:override '(baseline-skip . 1.5) #:center-column (
                                                    diagram-markup
                                                    hidden-plus 
                                                  )))))
                         
                         (set! (ly:music-property m 'articulations)
                               (append (ly:music-property m 'articulations)
                                       (list (make-music 'TextScriptEvent
                                                         'text final-markup
                                                         'direction 1))))))))))
       m)
     music))

twTabs =
#(define-music-function (music) (ly:music?)
   (add-tw-fingering (ly:music-deep-copy music)))