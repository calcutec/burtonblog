window.App = {
  Models: {},
  Collections: {},
  Views: {},
  Router: {}
};

// Post model
App.Models.Post = Backbone.Model.extend({
  urlRoot: '/poetry/portfolio',
  defaults: {
    header: '',
    body: ''
  },
  validate: function(attrs){
    if (!attrs.header){
        alert('Your post must have a header!');
    }
    if (attrs.body.length < 2){
        alert('Your post must have more than one letter!');
    }
  }
});

App.Views.Global = Backbone.View.extend({
    events: {
        'click #n-workshop': 'loadWorkshop',
        'click #n-portfolio': 'loadPortfolio'
    },
    loadWorkshop: function(e){
        e.preventDefault();
        App.Collections.Post.postCollection.clear_all()
        App.Views.Posts.poemListView.render()
    },
    loadPortfolio: function(e){
        e.preventDefault();
        App.Collections.Post.postCollection.clear_all()
        App.Collections.Post.myPostsCollection = App.Collections.Post.postCollection.byAuthor(14)
        App.Views.Posts.myPoemListView = new App.Views.Posts({collection: App.Collections.Post.myPostsCollection});
        App.Views.Posts.myPoemListView.render()
    },
});

// Post view
App.Views.Post = Backbone.View.extend({
    tagName: 'article',
    className: 'postArticle',
    events: {
        'click .edit':   'editPost',
        'click .edit-button':   'editPost',
        'click .submit-button':   'updatePost',
        'click .delete-button': 'deletePost',
        'click #n-workshop': 'loadWorkshopCollection'
    },
    initialize: function(){
        this.listenTo(this.model, "change", this.savePost); // calls render function once name changed
        this.listenTo(this.model, "destroy", this.removejunk); // calls remove function once model deleted
        this.listenTo(this.model, "removeMe", this.removejunk); // calls remove function once model deleted
    },
    savePost: function(){
        this.model.save(null, {
            success: function (model, response) {
                if (response.updatedsuccess == true){
                    return response;
                }
                if (response.savedsuccess == true){
                    new App.Views.Post({model:model}).render();
                    return response;
                }
                return response;
            },
            error: function () {
                alert('your poem did not save properly..')
            },
            wait: true
        });
    },
    editPost: function(e){
        e.preventDefault();
        if (!App.Views.Post.editable) {
            var $target = $(e.target);
            $target.closest("article").find(".edit-me").addClass('edit-selected');
            var editSelected = $('.edit-selected');
            App.Views.Post.currentwysihtml5 = editSelected.wysihtml5({
                toolbar: {
                    "style": true,
                    "font-styles": true,
                    "emphasis": true,
                    "lists": true,
                    "html": false,
                    "link": false,
                    "image": false,
                    "color": false,
                    fa: true
                }
            });
            $target.closest("article").find('.edit-button').html("Submit Changes").attr('class', 'submit-button').css({'color':'red', 'style':'bold'});
            editSelected.css({"border": "2px #2237ff dotted"});
            editSelected.attr('contenteditable', false);
            App.Views.Post.editable = true;
        }
    },
    updatePost: function(e){
        var $submittarget = $(e.target).closest("article").find(".edit-me");
        var content = $submittarget.html();
        $('.submit-button').html("Edit").attr('class', 'edit-button').css({'color':'#8787c1'});
        $('.wysihtml5-toolbar').remove();
        App.Views.Post.editable = false;
        $submittarget.css({"border":"none"});
        $submittarget.attr('contenteditable', false);
        $submittarget.removeClass("edit-selected wysihtml5-editor wysihtml5-sandbox");
        this.model.set({"body":content});
    },
    deletePost: function(e){
        e.preventDefault();
        alert("Do you really want to destroy this post?");
        var that = this;
        this.model.destroy({
          success: function() {
            console.log('model completely destroyed..');
          }
        });
    },
    removejunk: function(){
        // same as this.$el.remove();
        this.remove();
        // unbind events that are set on this view
        this.off();
        // remove all models bindings made by this view
        this.model.off( null, null, this );
    },
    render: function(){
        this.$el.html(this.model.attributes.post_widget); // calls the template
        $("#main").prepend(this.el);
    }
});

// Post collection
App.Collections.Post = Backbone.Collection.extend({
    url: '/poetry/portfolio',
    parse: function(response){return response.myPoems;},
    byAuthor: function (author_id) {
       var filtered = this.filter(function (post) {
           return post.get("author") === author_id;
       });
       return new App.Collections.Post(filtered);
    },
    clear_all: function(){
        this.each(function(model){
            model.trigger('removeMe');
        });
    }
});

// View for all posts (collection)
App.Views.Posts = Backbone.View.extend({ // plural to distinguish as the view for the collection
    attachToView: function(){
        this.el = $("#poem-list");
        var self = this;
        $("article").each(function(){
            var poemEl = $(this);
            var id = poemEl.find("span").text();
            var poem = self.collection.get(id);
            new App.Views.Post({
                model: poem,
                el: poemEl
            });
        });
    },
    render: function(){
        this.collection.each(function(Post){
            var postView = new App.Views.Post({model: Post});
            postView.render()
        });
    }
});


// Backbone router
App.Router = Backbone.Router.extend({
    routes: { // sets the routes
        '':         'start', // http://netbard.com/poetry/portfolio/
        'create': 'create', // http://netbard.com/poetry/portfolio/#create
        'edit/:id': 'edit' // http://netbard.com/poetry/portfolio/#edit/7
    },
    start: function(){
        console.log('now in view for reading poetry');
    },
    edit: function(id){
        console.log('edit route with id: ' + id);
    },
    create: function(id){
        console.log('View for creating poetry rendered');
    }
});

$.fn.serializeObject = function()
{
    var o = {};
    var a = this.serializeArray();
    $.each(a, function() {
        if (o[this.name] !== undefined) {
            if (!o[this.name].push) {
                o[this.name] = [o[this.name]];
            }
            o[this.name].push(this.value || '');
        } else {
            o[this.name] = this.value || '';
        }
    });
    return o;
};

App.Views.ModalDisplay = Backbone.View.extend({
    el: '#myPortfolio',
    events: {
        'click #open': 'openModal'
    },
    template: '<h1><button type="button" id="open" class="btn btn-info btn-lg">Create Poem</button></h1>',
    openModal: function() {
        var view = new App.Views.ModalView();
        new Backbone.BootstrapModal({
            content: view,
            title: 'Create a poem',
            animate: true,
            okText: 'Submit New Post',
            okCloses: true,
            enterTriggersOk: true
        }).open(function(){
            var poem_text = $('#editable').html();
            $('#show-form').html(poem_text);
            var $form = $('#poem-form');
            var data = $form.serializeObject();
            var newPostModel = new App.Models.Post(data);
            newPostModel.save(null, {
                success: function (model, response) {
                    new App.Views.Post({model:model}).render();
                    return response;
                },
                error: function () {
                    alert('your poem did not save properly..')
                },
                wait: true
            });
        });
    },
    render: function() {
        this.$el.html(this.template);
        console.log('main rendered');
        return this;
    }

});

App.Views.ModalView = Backbone.View.extend({
    template: _.template($('#formTemplate').html()),
    events: {
        'submit form': 'submit'
    },
    render: function() {
        this.$el.html(this.template);
        console.log('modal rendered');
        return this;
    }
});

    $(document).ready(function() {
    App.Views.ModalDisplay.modalDisplayView = new App.Views.ModalDisplay();
    App.Views.ModalDisplay.modalDisplayView.render();

    var csrftoken = $('meta[name=csrf-token]').attr('content');
    $(function(){
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken)
                }
            }
        })
    });

    App.Collections.Post.postCollection = new App.Collections.Post();
    App.Collections.Post.postCollection.fetch({
        success: function() {
            App.Views.Posts.poemListView = new App.Views.Posts({collection: App.Collections.Post.postCollection});
            App.Views.Posts.poemListView.attachToView();
        }
    });
    App.Views.Global.globalView = new App.Views.Global({el: '.page'});
    new App.Router();
    Backbone.history.start(); // start Backbone history
});


    ////adding individual models to collection
    //    var chihuahua = new App.Models.Post({header: 'Sugar', post: 'This this the name of my chihuahua'});
    //    var chihuahuaView = new App.Views.Post({model: chihuahua});
    //    var postCollection = new App.Collections.Post(); // only need to create the collection once
    //    postCollection.add(chihuahua);

    ////adding multiple models to collection////
    //    var postCollection = new App.Collections.Post([
    //     {
    //       header: 'Sugar',
    //       post: 'That is the name of my chihuahua',
    //     },
    //     {
    //       header: 'Gizmo',
    //       post: 'That is the name of my beagle'
    //     }
    //    ]);
    //    var postsView = new App.Views.Posts({collection: postCollection});
    //    postsView.render();
    //    sessionStorage.setItem('postCollection', JSON.stringify(postCollection));

    ////updating a single model in a collection
    //    postCollection.get(112).set({title: "No Longer Bob"});


    ////Retrieving models from flask database////
    //    postCollection.fetch({
    //        success: function() {
    //            postsView.render();
    //        }
    //    })

    ////Bootstrapping flask models on load////
    //    postCollection = new App.Collections.Post();
    //    $(function () {
    //        $('Article').each(function() {
    //            postCollection.add(new App.Models.Post($(this).data()));
    //        });
    //        postsView = new App.Views.Posts({collection: postCollection});
    //        //postsView.render()
    //    });