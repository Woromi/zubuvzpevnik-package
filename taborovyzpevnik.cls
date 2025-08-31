\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{taborovyzpevnik}[2025/06/07 Custom class for A5 booklet songbook]

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
% Language
% ==========================
\RequirePackage[czech]{babel}

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
\graphicspath{{\rootpath img/}} % Obrazky spolecne pro vsechny tabory

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

% ==========================
% Prevent page breaks inside songs
% ==========================
\RequirePackage{needspace}

% ==========================
% Front cover
% ==========================
\newcommand{\makefrontcover}{%
	\clearpage
	\pagestyle{empty}
	%	\includepdf[pages={1}]{Zpěvník 2025.pdf}
	\begin{titlepage}
		\centering
		\null\vfill
		{\fontsize{72}{75}\bfseries\setmainfont{SKAUT Bold} Zpěvník\par}
		\vfill
		\includegraphics{../img/kane}
		\vfill
		{\Large\setmainfont{TheMix C5 Bold} \@title~\the\year\par}
		\vfill
	\end{titlepage}
	
	% Inside front cover = TOC
	\clearpage
	\pagestyle{empty}
	{\large \showindex[1]{Obsah}{obsah}}
	
	% Start page numbering from the following page
	\clearpage
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
	\input{../akordy}
	\null\vfill
	\begin{center}
		{\small \ifx\relax#1\else #1 \\ \fi Sestavil: \@author~\the\year{}}
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
\RequirePackage{modulus}
\newcommand{\padbookletpages}[1][4]{%
	\clearpage
	\modulo{\numexpr \value{page}-1 \relax}{#1}%
	\newcounter{extrablankpages}%
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
}

\endinput
