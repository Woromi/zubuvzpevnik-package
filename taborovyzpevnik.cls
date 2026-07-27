\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{taborovyzpevnik}[2026-06-13 Custom class for A5 booklet songbook]

% ==========================
% Base class
% ==========================
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
% Page layout
% ==========================
\RequirePackage[
	tmargin=1.5cm,
	bmargin=1.5cm,
	lmargin=1cm,
	rmargin=1cm
]{geometry}

% ==========================
% Song styling overrides
% ==========================
\renewcommand{\zub@lyricfont}{\ttfamily}
\renewcommand{\zub@printchord}{\ttfamily\bfseries}
\renewcommand{\zub@stitlefont}{\Huge}

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
% Paragraph & spacing
% ==========================
\setlength{\parindent}{0pt} % No indent for song lines
\setlength{\parskip}{6pt} % Space between stanzas
\RequirePackage{setspace}
\onehalfspacing % Slightly spaced lines for readability

\multivoiceoff

% ==========================
% Prevent page breaks inside songs
% ==========================
\RequirePackage{needspace}

% ==========================
% Front cover
% ==========================
% Pin per book with \renewcommand{\campyear}{<year>} so old books rebuild unchanged.
\newcommand{\campyear}{\the\year}

% Pages the front matter took, for \padbookletpages to check (see there).
\newcounter{ZUB@frontpages}

% Optional argument: a hand-made cover PDF replacing the generated title page.
\newcommand{\makefrontcover}[1][]{%
	\clearpage
	\pagestyle{empty}
	\ifblank{#1}{%
		\begin{titlepage}
			\centering
			\vspace*{-21pt}
			{\fontsize{72}{75}\bfseries\setmainfont{SKAUT Bold} Zpěvník\par}
			\vspace{16pt}
			\includegraphics[width=350pt]{img/kane}\par
			\vfill
			% Camp name centered; year below it, flush right
			{\large\setmainfont{TheMix C5 Bold}\@title\par}
			\vspace{3pt}
			\makebox[\textwidth][r]{\small\setmainfont{TheMix C5 SemiLight}\campyear}
		\end{titlepage}
	}{%
		\includepdf[pages={1}]{#1}%
	}%

	% Inside front cover = TOC
	\clearpage
	\pagestyle{empty}
	{\large \showindex[1]{Obsah}{obsah}}

	% Start page numbering from the following page
	\clearpage
	% For \padbookletpages; the reset below would otherwise hide this from it
	\setcounter{ZUB@frontpages}{\numexpr\value{page}-1\relax}%
	\pagestyle{fancy}
	\setcounter{page}{1}
}

% ==========================
% Back cover
% ==========================
\newcommand{\makebackcover}[1][]{%
	% --- Inside Back Cover ---
	\clearpage
	\pagestyle{empty}
	\input{akordy}
	\null\vfill
	\begin{center}
		{\small \ifblank{#1}{}{#1 \\ }Sestavil: \@author~\campyear{}}
	\end{center}
	\null

	% --- Back Cover ---
	\clearpage
	\pagestyle{empty}
	\newpage\ \newpage % keep space for back cover
}

% ==========================
% Fill booklet pages (multiple of 4)
% ==========================
% Pads songs to a multiple of #1, giving 2 + 4n + 2 overall; only valid while
% the front matter is 2 pages. docs/internals.md#document-classes-and-booklet-page-maths
\RequirePackage{modulus}
\newcounter{extrablankpages}
\newcommand{\padbookletpages}[1][4]{%
	\clearpage
	\modulo{\numexpr \value{page}-1 \relax}{#1}%
	\ifnum\remainder=0
		\setcounter{extrablankpages}{0}%
	\else
		\setcounter{extrablankpages}{\numexpr #1 - \remainder \relax}%
	\fi
	\loop
	\ifnum\value{extrablankpages}>0
	\pagestyle{fancy}
	\null\newpage
	\addtocounter{extrablankpages}{-1}%
	\repeat
	\ifnum\value{ZUB@frontpages}=\tw@\else
		\ClassWarning{taborovyzpevnik}{Front matter is
			\theZUB@frontpages\space page(s), not 2, so the book will not come out a
			multiple of 4 pages and makebooklet.sh will refuse to impose it.
			Shorten the index or pad the front matter to 2 pages}%
	\fi
}

\endinput
