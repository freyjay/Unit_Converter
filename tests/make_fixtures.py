#!/usr/bin/env python3
"""Writes the regression fixtures into the current directory. Deterministic."""
import random; random.seed(1)
rows=["%d %.4f %.4f %.4f \"GRND\"\r\n"%(i,19857+random.random()*300,20260+random.random()*900,95+random.random()*7) for i in range(1,41)]
rows[5]='6 19900.1234 20300.5678 100.0000 "EDGE OF PVMT"\r\n'
open('penzd.txt','w',newline='').write(''.join(rows))
open('lf.csv','w',newline='').write("E,N,Z\n3540.111,3517.240,29.423\n7063.658,4814.928,92.881")
open('bom.txt','wb').write(b'\xef\xbb\xbf'+b'1 100.5 200.5 10.25 "A"\n2 101.5 201.5 11.25 "B"\n')
open('nonfinite.txt','w').write('1e309 20.25 30.75\n')
open('sci.txt','w').write('1.2345e-5 2.3456e-5 3.4567e-5\n')
open('onebad.txt','w').write(''.join('%d %.4f %.4f %.4f "G"\n'%(i,19800+i*1.5,20200+i*2.5,95+i*.01) for i in range(1,100))+'100 19900 x 96 "G"\n')
open('gapped.txt','w').write('1 100.25 200.25 10.25 GRND\n3 101.25 201.25 11.25 GRND\n7 102.25 202.25 12.25 GRND\n'*4)
open('bigint.txt','w').write('9007199254740993 1 2\n'*12)
open('mixednl.txt','wb').write(b'1 10.5 20.5 30.5 A\r\n2 11.5 21.5 31.5 B\n3 12.5 22.5 32.5 C\r\n')
open('spaces.txt','w').write('  1   10.5   20.5   30.5   "TOP OF  CURB"  \n')
open('latin1.txt','wb').write(b'1 10.5 20.5 30.5 Caf\xe9\n')
open('quoted.csv','w').write('1,"10.5",20.5,30.5,"Curb, top"\n2,11.5,21.5,31.5,"He said ""hi"""\n')
open('deccomma.txt','w').write('1 19857,2577 20260,4556 100,3058 GRND\n')
open('deccomma2.csv','w').write('1,19857,2577,20260,4556,100,3058,GRND\n')
open('intcoords.txt','w').write(''.join('%d %d %d %d\n'%(i,1000+i,2000+i,10) for i in range(1,15)))
open('tie.txt','w').write('1 0.5 1.5 2.5\n')
open('neg.txt','w').write('1 -0.00001 -10.25 +5\n')
print('fixtures written')
