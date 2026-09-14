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
% A5 body
% ==========================
% Geometry, song fonts and spacing live in one file so this class and
% malyzpevnik cannot drift apart -- pap={a5} has to mean one thing.
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
% Prevent page breaks inside songs
% ==========================
\RequirePackage{needspace}

% ==========================
% Front cover
% ==========================
% Pin per book with \renewcommand{\campyear}{<year>} so old books rebuild unchanged.
\newcommand{\campyear}{\the\year}

% The cover faces are Junák-licensed and deliberately not in the repo, so treat
% them as optional: docs/building.md#cover-fonts
\newcommand{\ZUB@coverfont}[1]{%
	\IfFontExistsTF{#1}{\setmainfont{#1}}%
		{\ClassWarning{taborovyzpevnik}{Cover font '#1' is not installed;
			setting that line in the text font instead}}%
}

% Fixed height for the cover title, so a substitute font's descender cannot
% lengthen the title page and spill the front matter onto a third page --
% which would break the 2 + 4n + 2 booklet paging.
\newlength{\ZUB@covertitleheight}
\setlength{\ZUB@covertitleheight}{66.96pt}

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
			\vbox to \ZUB@covertitleheight{%
				\centering{\fontsize{72}{75}\bfseries\ZUB@coverfont{SKAUT Bold} Zpěvník\par}\vss}
			\vspace{16pt}
			\includegraphics[width=350pt]{img/kane}\par
			\vfill
			% Camp name centered; year below it, flush right
			{\large\ZUB@coverfont{TheMix C5 Bold}\@title\par}
			\vspace{3pt}
			\makebox[\textwidth][r]{\small\ZUB@coverfont{TheMix C5 SemiLight}\campyear}
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
