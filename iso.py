import struct,sys
f=open(sys.argv[1],'rb')
def rd(lba,n):
    f.seek(lba*2048);return f.read(n)
pvd=rd(16,2048)
print('ID',pvd[1:6],'sys',pvd[8:40].strip(),'vol',pvd[40:72].strip())
root=pvd[156:190]
def walk(lba,size,path):
    data=rd(lba,size);i=0
    while i<len(data):
        l=data[i]
        if l==0:
            i=(i//2048+1)*2048;continue
        r=data[i:i+l];i+=l
        elba,=struct.unpack('<I',r[2:6]);esz,=struct.unpack('<I',r[10:14]);fl=r[25];nl=r[32];name=r[33:33+nl]
        if name in(b'\0',b'\1'):continue
        name=name.decode('latin1').split(';')[0]
        p=path+'/'+name
        if fl&2: walk(elba,esz,p)
        else: print(f'{elba:8d} {esz:11d} {p}')
walk(struct.unpack('<I',root[2:6])[0],struct.unpack('<I',root[10:14])[0],'')
