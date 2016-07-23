Bootcast -- using multicast to distribute files to multiple nodes
=================================================================

bootcast is a file transport protocol that reduces bandwidth when
multiple clients request access to the same files at once. This 
can be useful for instance when netbooting multiple nodes in a single
cluster. Using a different file transport protocol like (T)FTP or HTTP
will quickly saturate the network when more clients boot at the same 
time.

Design notes
------------
bootcast was designed as a drop-in replacement for (T)FTP or HTTP based
clients like wget or curl. A bootcast client can simply request a file
from a bootcast server and the file will be downloaded. This is different
from most other multicast implementations where a file is simply pushed
to different clients.

Behind the scenes the initial bootcast request will trigger to send 
the bootcast server to start a broadcast of the requested file. The 
bootcast server will respond with the connection details for the 
client in order to join the TCP multicast group. Subsequent requests
will not trigger a new read from the file, but will simply join in the
existing multicast group. 

When a client has received all pages from the bootcast server it will
send a request indicating that it will leave the broadcast. When all
clients have left the bootcast the bootcast server will stop the cast.
Also, when several iterations of bootcasts have occurred without new
join requests or leave requests, the bootcast server will stop the
broadcast.

Protocol notes
--------------
A client can request a bootcast file by peforming a join request. This
is a simple HTTP GET request like this `GET /join/<path>`. The server
will respond with a text document containing the following lines:

    CONNECT=<multicast_group>:<port>
    TOKEN=<a client session identifier>
    PAGES=<the number of pages or file blocks>
    PAGESIZE=<the size of each block in bytes>

The client can then `bind` to a listening socket as described in the CONNECT 
string. Each block of data sent by the server will have the following data 
fields. 

1. a four byte integer containing the size of the current page.
2. a four byte integer containing the page index (starting with 1)
3. a four byte integer which is reserved for future expansion.
4. a four byte integer which is reserved for future expansion.
 
Each value will be transferred in network byte order.

Once the client has downloaded all pages from the server, it will leave the cast.
This is done by sending a HTTP GET request like `GET /leave/<path>`. The client
must identify itself by providing an HTTP X-TOKEN header containing the client
session identifier. If the client does not provide this header, its request will
be ignored. No response body will be sent back to the client.

Reference implementation
------------------------
A simple reference implementation of the bootcast protocol can be downloaded
from http://github.com/hansthen/bootcast. This will install a sample bootcast
client and a sample bootcast server. 
