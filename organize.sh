#!/bin/bash

cp -r results snapshot_results

echo "preparing to organize \'snapshot_results/\' by filetype.";

mkdir res_html res_doc res_pdf
#mkdir other;
cd snapshot_results;

echo "moving html documents..."
find ./ -type f -name '*.html' -exec cp {} ../res_html/ \;
find ./ -type f -name '*.htm' -exec cp {} ../res_html/ \;
echo "moving word documents..."
find ./ -type f -name '*.doc*' -exec cp {} ../res_doc/ \;
echo "moving pdfs..."
find ./ -type f -name '*.pdf' -exec cp {} ../res_pdf/ \;
#echo "moving other files..."
#find ./ -type f -name '*' -exec cp {} ../other/ \;

mv ../res_html ./
mv ../res_doc ./
mv ../res_pdf ./
#mv ../other ./
#rmdir *
rm *.zip

find ./res_html -type f -print0 | xargs -0 zip ./htmls.zip -@
find ./res_doc -type f -print0 | xargs -0 zip ./docs.zip -@
find ./res_pdf -type f -print0 | xargs -0 zip ./pdfs.zip -@
#find ./other -type f -print0 | xargs -0 zip ./other.zip -@

rm -r ./res_html ./res_doc ./res_pdf
#rm ./other
mv htmls.zip ../results_htmls.zip
mv docs.zip ../results_docs.zip
mv pdfs.zip ../results_pdfs.zip
cd ../

cp -r qa_dir snapshot_qa
echo "preparing to organize \'snapshot_qa/\' by filetype.";

mkdir qa_html qa_doc qa_pdf 
#mkdir other;
cd snapshot_qa;

echo "moving html documents..."
find ./ -type f -name '*.html' -exec cp {} ../qa_html/ \;
find ./ -type f -name '*.htm' -exec cp {} ../qa_html/ \;
echo "moving word documents..."
find ./ -type f -name '*.doc*' -exec cp {} ../qa_doc/ \;
echo "moving pdfs..."
find ./ -type f -name '*.pdf' -exec cp {} ../qa_pdf/ \;
#echo "moving other files..."
#find ./ -type f -name '*' -exec cp {} ../other/ \;

mv ../qa_html ./
mv ../qa_doc ./
mv ../qa_pdf ./
#mv ../other ./
#rmdir *
rm *.zip

find ./qa_html -type f -print0 | xargs -0 zip ./htmls.zip -@
find ./qa_doc -type f -print0 | xargs -0 zip ./docs.zip -@
find ./qa_pdf -type f -print0 | xargs -0 zip ./pdfs.zip -@
#find ./other -type f -print0 | xargs -0 zip ./other.zip -@

rm -r ./qa_html ./qa_doc ./qa_pdf
#rm .other
mv htmls.zip ../qa_htmls.zip
mv docs.zip ../qa_docs.zip
mv pdfs.zip ../qa_pdfs.zip

cd ../;
echo "done!";
