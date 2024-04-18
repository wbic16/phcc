#!/bin/bash
echo "--------------------"
echo "Phext Slurper v1.0"
echo "(c) 2024 Phext, Inc."
echo "--------------------"
LB=1
SF=1
SR=1
CN=1
VM=1
BK=1
CH=1
SN=1
SC=1

# Find all relevant source files
ls -1 configure >.slurp-plan
ls -1 Makefile* >>.slurp-plan
find . -name '*.h' -print >>.slurp-plan
find . -name '*.c*' -print >>.slurp-plan

# Generate the index
SCROLL_BREAK='\x17'
echo "INDEX: $LB.$SF.$SR/$CN.$VM.$BK/$CH.$SN.$SC">.slurp-output
SC=2
while read file; do
  echo "${file}: $LB.$SF.$SR/$CN.$VM.$BK/$CH.$SN.$SC">>.slurp-output
  SC=$(($SC + 1))
done <.slurp-plan
echo -ne $SCROLL_BREAK >>.slurp-output

# Slurp all the content
SC=2
while read file; do
  cat $file >>.slurp-output
  echo -ne $SCROLL_BREAK >>.slurp-output
  echo "${file}: #$SC"
  SC=$(($SC + 1))
done <.slurp-plan
mv .slurp-output monolith.phext
echo "Monolith Ready"