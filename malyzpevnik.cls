\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{malyzpevnik}[2026-09-15 Class for the A5 hand-bound songbook]

% ==========================
% Base class
% ==========================
% The same page as taborovyzpevnik, so a song's pap={a5} means one thing.
\LoadClass[a5paper,twoside,10pt]{book}

% ==========================
% Option handling
% ==========================
\DeclareOption*{%
	\PassOptionsToPackage{\CurrentOption}{zubuvzpevnik}%
}
\ProcessOptions\relax

% ==========================
% Load base package
% ==========================
\RequirePackage{zubuvzpevnik}

% ==========================
% A5 body
% ==========================
% Geometry, song fonts and spacing are shared with taborovyzpevnik; this is the
% text block every pap={a5} was measured against, so it must not be overridden.
\input{a5layout.cfg}

% ==========================
% Images
% ==========================
\RequirePackage{pdfpages}
\RequirePackage{graphicx}
\graphicspath{{img/}}

% ==========================
% Header/Footer
% ==========================
\RequirePackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[LE,RO]{\thepage} % Page numbers on outer corners
\renewcommand{\headrulewidth}{0pt} % no header line
\renewcommand{\footrulewidth}{0pt} % no footer line

% ==========================
% Title page
% ==========================
% The book is bound by hand with no printed case, so this is the first page
% inside rather than a cover, and it is page 1 of one arabic sequence that runs
% to the last page -- only the folio is held back here. The optional argument
% takes an image for it; there is none today. docs/building.md
\newcommand{\maketitlepage}[1][]{%
	\thispagestyle{empty}%
	\null\vfill
	\begin{center}
		{\fontsize{34}{40}\selectfont\bfseries\@title\par}
		\ifblank{#1}{}{\vspace{1cm}\includegraphics[width=0.8\linewidth]{#1}\par}%
	\end{center}
	\vfill\null
	\clearpage
	% The title keeps its own leaf so the songs open on a right-hand page; the
	% test only adds the blank when the next page would be a verso, so removing
	% \bindingleaf cannot leave a stray one behind. docs/internals.md
	\if@twoside
		\ifodd\c@page\else\thispagestyle{empty}\null\newpage\fi
	\fi
}

% The imprint (tiráž), on the last page as Czech books have it: who, when, how,
% in small type at the foot. It sets no page of its own -- \bindingleaf[\makeimprint]
% puts it on the back leaf's free face. \imprintnote adds a line of your own.
\newcommand{\zub@imprintnote}{}
\newcommand{\imprintnote}[1]{\def\zub@imprintnote{#1}}
\newcommand{\makeimprint}{%
	\null\vfill
	{\small\raggedright
		\textbf{\@title}\par
		Sestavil: \@author\par
		Vydání: \@date\par
		\ifx\zub@imprintnote\@empty\else\zub@imprintnote\par\fi
		\medskip
		{\footnotesize Vysázeno v~LuaLaTeXu (balík songs), notové ukázky v~LilyPondu.\par
		Texty a~akordy patří jejich autorům; zpěvník je určen k~soukromému
		použití.\par}%
	}%
}

% ==========================
% Indexes
% ==========================
% At the end, and not only by convention: the page numbers run unbroken from
% page 1, so an index at the front would shift every song page number it
% records and the two LuaLaTeX passes would never converge. Two columns: the
% entries are short enough that the dot leaders absorb the lost width, and it
% halves the index -- 13 pages to 7.
\newcommand{\insertindex}{%
	\clearpage
	% songs.sty ends an index line with \rightskip2em and then pulls the page
	% number back out with \kern-2em, so a reference wider than 2em hangs past
	% the line; two columns also come out a hair wider than the text block.
	% Taking the index in slightly narrows both columns and absorbs the hang.
	\begingroup\addtolength{\hsize}{-8pt}%
	{\large \showindex[2]{Obsah}{obsah}}
	{\large \showindex[2]{Obsah podle interpreta}{obsahAutor}}%
	\endgroup
}

% ==========================
% Binding leaves
% ==========================
% The case is glued straight onto the outer leaf at each end of the block, so
% that leaf carries nothing: the pasted side vanishes under the board and the
% side facing the reader is stuck to it and never turns. One blank leaf (two
% pages) at each end keeps content off it. Harmless if separate endpapers are
% used instead -- it is then the flyleaf. See docs/internals.md.
% The optional argument fills the leaf's first page, which only at the back is
% the face left visible -- where the imprint goes. At the front it is glued.
\newcommand{\bindingleaf}[1][]{%
	\clearpage
	\thispagestyle{empty}\null#1\newpage
	\thispagestyle{empty}\null\newpage
}

% ==========================
% Fill out the last sheet
% ==========================
% Every sheet of paper carries four pages, so the book has to end on a multiple
% of four or the last sheet comes out half empty and unfoldable. Signatures are
% cut from that page count afterwards by scripts/makebook.sh, which is why this
% pads to 4 and not to a whole signature -- docs/internals.md.
% The filler runs after \bindingleaf, so it has to be as blank as the leaf is:
% a folio on the last page would be printed onto the surface the board covers.
\newcommand{\padbookpages}[1][4]{\zub@padpages{#1}{\thispagestyle{empty}}}

\endinput
