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
		{\Huge\bfseries\@title\par}
		\vspace{1cm}
		\ifblank{#1}{}{\includegraphics[width=0.8\linewidth]{#1}\par\vspace{1cm}}%
		{\large\@author\par}
		\vspace{6pt}
		{\large\@date\par}
	\end{center}
	\vfill\null
	\clearpage
}

% ==========================
% Indexes
% ==========================
% At the end, and not only by convention: the page numbers run unbroken from
% page 1, so an index at the front would shift every song page number it
% records and the two LuaLaTeX passes would never converge. One column, because
% an A5 text block is too narrow to split an index title and its dot leaders.
\newcommand{\insertindex}{%
	\clearpage
	{\large \showindex[1]{Obsah}{obsah}}
	{\large \showindex[1]{Obsah podle interpreta}{obsahAutor}}
}

% ==========================
% Fill out the last sheet
% ==========================
% Every sheet of paper carries four pages, so the book has to end on a multiple
% of four or the last sheet comes out half empty and unfoldable. Signatures are
% cut from that page count afterwards by scripts/makebook.sh, which is why this
% pads to 4 and not to a whole signature -- docs/internals.md.
\newcommand{\padbookpages}[1][4]{\zub@padpages{#1}{}}

\endinput
